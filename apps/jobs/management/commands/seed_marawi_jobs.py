from django.core.management.base import BaseCommand

from apps.jobs.models import Job, JobCategory
from apps.users.models import Barangay, Role, User, UserProfile


BARANGAYS = [
    "Bangon",
    "Basak Malutlut",
    "Bubonga Lilod",
    "Bubonga Punod",
    "Cabasaran",
    "Calocan East",
    "Calocan West",
    "Datu Naga",
    "Dansalan",
    "Fort",
    "Lilod Madaya",
    "Marawi Poblacion",
    "Matampay",
    "Moncado Colony",
    "Pagayawan",
    "Pantaon",
    "Rorogagus East",
    "Rorogagus Proper",
    "Saber",
    "Sagonsongan",
]

JOBS = [
    ("Construction", "Mason", "2 years masonry experience, can read simple plans."),
    ("Construction", "Carpenter", "Experience in roofing and framing work."),
    ("Construction", "Electrician Helper", "Basic electrical safety knowledge."),
    ("Retail", "Store Cashier", "Good customer service and basic math."),
    ("Retail", "Inventory Clerk", "Can encode stock and perform daily counts."),
    ("Food", "Cook", "Can prepare local meals and keep kitchen clean."),
    ("Food", "Kitchen Assistant", "Willing to handle prep and cleanup tasks."),
    ("Transport", "Delivery Rider", "Valid license and route familiarity."),
    ("Transport", "Driver", "Professional license and clean driving record."),
    ("Education", "Tutor", "Can teach Math/English for elementary students."),
    ("Healthcare", "Caregiver", "Patient care experience preferred."),
    ("Admin", "Office Assistant", "Document filing and MS Office basics."),
    ("Admin", "Encoder", "Fast typing and attention to detail."),
    ("IT", "Computer Technician", "Basic troubleshooting and networking."),
    ("Services", "Barber", "Can provide haircut and grooming services."),
    ("Services", "Tailor", "Can do measurements and uniform alterations."),
    ("Sales", "Field Sales Agent", "Strong communication and persuasion skills."),
    ("Cleaning", "Housekeeping Staff", "Reliable and detail-oriented."),
    ("Security", "Security Guard", "With valid license preferred."),
    ("Agriculture", "Farm Worker", "Can handle planting and harvesting tasks."),
]


class Command(BaseCommand):
    help = "Seed Marawi local job data for development and demos."

    def handle(self, *args, **options):
        for name in BARANGAYS:
            Barangay.objects.get_or_create(name=name)

        employer, _ = User.objects.get_or_create(
            username="marawi_employer",
            defaults={"email": "employer@marawi.local"},
        )
        employer.set_password("Password123!")
        employer.save(update_fields=["password"])

        seeker, _ = User.objects.get_or_create(
            username="marawi_seeker",
            defaults={"email": "seeker@marawi.local"},
        )
        seeker.set_password("Password123!")
        seeker.save(update_fields=["password"])

        first_barangay = Barangay.objects.order_by("id").first()
        UserProfile.objects.update_or_create(
            user=employer,
            defaults={
                "role": Role.EMPLOYER,
                "phone_number": "09170000001",
                "barangay": first_barangay,
            },
        )
        UserProfile.objects.update_or_create(
            user=seeker,
            defaults={
                "role": Role.SEEKER,
                "phone_number": "09170000002",
                "barangay": first_barangay,
            },
        )

        employer_profile = employer.profile
        barangays = list(Barangay.objects.all())
        for idx, (category_name, title, reqs) in enumerate(JOBS):
            category, _ = JobCategory.objects.get_or_create(name=category_name)
            barangay = barangays[idx % len(barangays)]
            Job.objects.get_or_create(
                employer=employer_profile,
                title=f"{title} - {barangay.name}",
                defaults={
                    "category": category,
                    "description": (
                        f"Local hiring in {barangay.name}, Marawi City. "
                        f"Open for immediate start."
                    ),
                    "requirements": reqs,
                    "location_text": f"{barangay.name}, Marawi City",
                    "salary_min": 450.00,
                    "salary_max": 900.00,
                    "status": Job.Status.OPEN,
                    "is_active": True,
                },
            )

        self.stdout.write(self.style.SUCCESS("Seeded Marawi jobs successfully."))
