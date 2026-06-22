from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from rest_framework import generics, permissions, status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import (
    AccountSetupToken,
    ApplicationEditToken,
    ApplicationStatus,
    ApplicationStatusHistory,
    MerchantApplication,
    RiderApplication,
)
from .serializers import (
    AccountSetupSerializer,
    ApplicationEditSerializer,
    ApplicationIdSerializer,
    MerchantApplicationSerializer,
    RejectApplicationSerializer,
    RequestChangesSerializer,
    RiderApplicationSerializer,
)
from .services import ApplicationService, application_type, get_application


def get_application_or_404(application_id):
    try:
        return get_application(application_id)
    except (MerchantApplication.DoesNotExist, RiderApplication.DoesNotExist, ValidationError):
        from django.http import Http404

        raise Http404("Application not found.")


def next_action_for(application):
    return {
        ApplicationStatus.PENDING: "Wait for admin review.",
        ApplicationStatus.UNDER_REVIEW: "Your application is being reviewed.",
        ApplicationStatus.APPROVED: "Check your email for the account setup link.",
        ApplicationStatus.REJECTED: "Review the rejection reason.",
        ApplicationStatus.REQUEST_CHANGES: "Update the requested fields using the secure edit link sent to your email.",
    }.get(application.status, "")


def latest_edit_url(request, application):
    token = (
        ApplicationEditToken.objects.filter(
            application_id=application.application_id,
            application_type=application_type(application),
            revoked_at__isnull=True,
        )
        .order_by("-created_at")
        .first()
    )
    if not token or not token.is_active:
        return None
    return request.build_absolute_uri(reverse("v1:onboarding-application-edit", kwargs={"token": token.token}))


def status_payload(request, application):
    payload = {
        "application_id": application.application_id,
        "type": application_type(application),
        "status": application.status,
        "submitted_at": application.created_at,
        "updated_at": application.updated_at,
        "applicant_name": application.applicant_name,
        "admin_remarks": application.admin_remarks or "",
        "next_action": next_action_for(application),
        "can_edit": application.status == ApplicationStatus.REQUEST_CHANGES,
        "edit_url": latest_edit_url(request, application) if application.status == ApplicationStatus.REQUEST_CHANGES else None,
    }
    if isinstance(application, MerchantApplication):
        payload["business_name"] = application.business_name
    return payload


def public_success_payload(application, message, confirmation_email_sent):
    return {
        "application_id": application.application_id,
        "status": application.status,
        "message": message,
        "confirmation_email_sent": confirmation_email_sent,
    }


class MerchantApplicationCreateView(generics.CreateAPIView):
    serializer_class = MerchantApplicationSerializer
    permission_classes = [permissions.AllowAny]
    parser_classes = [MultiPartParser, FormParser]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        application = serializer.save(status=ApplicationStatus.PENDING)
        confirmation_sent = ApplicationService.send_submission_confirmation(application)
        return Response(
            public_success_payload(application, "Merchant application submitted for review.", confirmation_sent),
            status=status.HTTP_201_CREATED,
        )


class RiderApplicationCreateView(generics.CreateAPIView):
    serializer_class = RiderApplicationSerializer
    permission_classes = [permissions.AllowAny]
    parser_classes = [MultiPartParser, FormParser]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        application = serializer.save(status=ApplicationStatus.PENDING)
        confirmation_sent = ApplicationService.send_submission_confirmation(application)
        return Response(
            public_success_payload(application, "Rider application submitted for review.", confirmation_sent),
            status=status.HTTP_201_CREATED,
        )


class MerchantStatusCheckView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = ApplicationIdSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        application = get_object_or_404(MerchantApplication, application_id=serializer.validated_data["application_id"])
        return Response(status_payload(request, application))


class RiderStatusCheckView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = ApplicationIdSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        application = get_object_or_404(RiderApplication, application_id=serializer.validated_data["application_id"])
        return Response(status_payload(request, application))


class MerchantApplicationDetailView(generics.RetrieveAPIView):
    serializer_class = MerchantApplicationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return MerchantApplication.objects.filter(applicant=self.request.user)


class RiderApplicationDetailView(generics.RetrieveAPIView):
    serializer_class = RiderApplicationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return RiderApplication.objects.filter(applicant=self.request.user)


class AdminApplicationListView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        app_type = request.query_params.get("type", "all").lower()
        status_filter = request.query_params.get("status", "all").upper()
        search = request.query_params.get("search", "").strip().lower()
        ordering = request.query_params.get("ordering", "newest")
        page = int(request.query_params.get("page", "1"))
        page_size = int(request.query_params.get("page_size", "20"))

        applications = []
        if app_type in ("merchant", "all"):
            applications.extend(MerchantApplication.objects.all())
        if app_type in ("rider", "all"):
            applications.extend(RiderApplication.objects.all())

        if status_filter != "ALL":
            applications = [app for app in applications if app.status == status_filter]
        if search:
            applications = [
                app
                for app in applications
                if search in app.application_id.lower()
                or search in app.applicant_name.lower()
                or search in getattr(app, "business_name", "").lower()
            ]

        applications.sort(key=lambda app: app.created_at, reverse=ordering != "oldest")
        paginator = Paginator(applications, page_size)
        page_obj = paginator.get_page(page)
        return Response(
            {
                "count": paginator.count,
                "results": [
                    {
                        "application_id": app.application_id,
                        "type": application_type(app),
                        "display_name": getattr(app, "business_name", app.applicant_name),
                        "status": app.status,
                        "submitted_at": app.created_at,
                        "service_zone": app.barangay,
                    }
                    for app in page_obj.object_list
                ],
            }
        )


class AdminApplicationDetailView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def get(self, request, application_id):
        application = get_application_or_404(application_id)
        serializer = MerchantApplicationSerializer(application) if isinstance(application, MerchantApplication) else RiderApplicationSerializer(application)
        histories = ApplicationStatusHistory.objects.filter(application_id=application.application_id)
        return Response(
            {
                "application_id": application.application_id,
                "type": application_type(application),
                "status": application.status,
                "data": serializer.data,
                "admin_remarks": application.admin_remarks or "",
                "requested_fields": application.requested_fields,
                "status_history": [
                    {
                        "from_status": history.from_status,
                        "to_status": history.to_status,
                        "remarks": history.remarks,
                        "actor": history.actor_id,
                        "created_at": history.created_at,
                    }
                    for history in histories
                ],
            }
        )


class AdminDocumentView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def get(self, request, application_id, document_key):
        application = get_application_or_404(application_id)
        document = getattr(application, document_key, None)
        if not document:
            return Response({"detail": "Document not found."}, status=status.HTTP_404_NOT_FOUND)
        if request.query_params.get("download") == "1":
            return FileResponse(document.open("rb"), as_attachment=False, filename=document.name.split("/")[-1])
        return Response(
            {
                "file_name": document.name.split("/")[-1],
                "content_type": getattr(document.file, "content_type", "application/octet-stream"),
                "size": document.size,
                "url": request.build_absolute_uri(document.url),
            }
        )


class AdminApproveApplicationView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def post(self, request, application_id):
        application = get_application_or_404(application_id)
        if isinstance(application, MerchantApplication):
            result = ApplicationService.approve_merchant(application, actor=request.user)
        else:
            result = ApplicationService.approve_rider(application, actor=request.user)
        token = getattr(result, "token", None)
        return Response({"application_id": application.application_id, "status": ApplicationStatus.APPROVED, "setup_token": str(token) if token else None})


class AdminRequestChangesView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def post(self, request, application_id):
        serializer = RequestChangesSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        application = get_application_or_404(application_id)
        edit_token = ApplicationService.request_changes(
            application,
            serializer.validated_data["admin_remarks"],
            serializer.validated_data["requested_fields"],
            actor=request.user,
        )
        return Response({"application_id": application.application_id, "status": ApplicationStatus.REQUEST_CHANGES, "edit_token": str(edit_token.token)})


class AdminRejectApplicationView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def post(self, request, application_id):
        serializer = RejectApplicationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        application = get_application_or_404(application_id)
        ApplicationService.reject_application(application, serializer.validated_data["admin_remarks"], actor=request.user)
        return Response({"application_id": application.application_id, "status": ApplicationStatus.REJECTED})


class ApplicationEditTokenView(APIView):
    permission_classes = [permissions.AllowAny]
    parser_classes = [MultiPartParser, FormParser]

    def get_token(self, token):
        edit_token = get_object_or_404(ApplicationEditToken, token=token)
        if not edit_token.is_active:
            return None
        return edit_token

    def get(self, request, token):
        edit_token = self.get_token(token)
        if not edit_token:
            return Response({"detail": "Edit token is expired or revoked."}, status=status.HTTP_400_BAD_REQUEST)
        application = get_application_or_404(edit_token.application_id)
        serializer = MerchantApplicationSerializer(application) if isinstance(application, MerchantApplication) else RiderApplicationSerializer(application)
        return Response(
            {
                "application_id": application.application_id,
                "type": application_type(application),
                "status": application.status,
                "requested_fields": edit_token.requested_fields,
                "admin_remarks": application.admin_remarks,
                "application": serializer.data,
            }
        )

    def patch(self, request, token):
        edit_token = self.get_token(token)
        if not edit_token:
            return Response({"detail": "Edit token is expired or revoked."}, status=status.HTTP_400_BAD_REQUEST)
        validation_serializer = ApplicationEditSerializer(data=request.data, context={"edit_token": edit_token})
        validation_serializer.is_valid(raise_exception=True)
        application = get_application_or_404(edit_token.application_id)
        serializer_class = MerchantApplicationSerializer if isinstance(application, MerchantApplication) else RiderApplicationSerializer
        serializer = serializer_class(application, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save(status=ApplicationStatus.PENDING, admin_remarks="", requested_fields=[])
        edit_token.revoke()
        return Response(status_payload(request, application))


class AccountSetupView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, token):
        setup_token = get_object_or_404(AccountSetupToken, token=token)
        if not setup_token.is_active:
            return Response({"detail": "Account setup token is expired or used."}, status=status.HTTP_400_BAD_REQUEST)
        application = get_application_or_404(setup_token.application_id)
        return Response(
            {
                "application_id": application.application_id,
                "type": application_type(application),
                "status": application.status,
                "email": application.company_email if isinstance(application, MerchantApplication) else application.email,
                "expires_at": setup_token.expires_at,
            }
        )

    def post(self, request, token):
        setup_token = get_object_or_404(AccountSetupToken, token=token)
        serializer = AccountSetupSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            user = ApplicationService.complete_account_setup(
                setup_token,
                serializer.validated_data["username"],
                serializer.validated_data["password"],
            )
        except ValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"username": user.username, "message": "Account setup completed."}, status=status.HTTP_201_CREATED)
