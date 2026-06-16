from celery import shared_task
from django.utils import timezone
from datetime import timedelta
from .models import Order, OrderStatus
from apps.payments.models import PaymentMethod, PaymentStatus
from apps.payments.services import PayMongoService
from apps.users.notifications import PushNotificationService
import logging

logger = logging.getLogger(__name__)


def _attempt_order_refund(order):
    payment_tx = order.payment_attempts.filter(
        status=PaymentStatus.SUCCESS,
        payment_method=PaymentMethod.PAYMONGO,
    ).first()
    if not payment_tx or not payment_tx.payment_id:
        return False
    try:
        PayMongoService.create_refund(
            payment_id=payment_tx.payment_id,
            amount=payment_tx.amount,
            reason="requested_by_customer",
        )
        payment_tx.status = PaymentStatus.REFUNDED
        payment_tx.save(update_fields=["status", "updated_at"])
        return True
    except Exception as exc:
        logger.warning("Auto-refund failed for order %s: %s", order.id, exc)
        return False

@shared_task
def auto_cancel_stale_orders():
    """
    Background task to cancel orders that merchants haven't accepted within 10 minutes.
    """
    ten_minutes_ago = timezone.now() - timedelta(minutes=10)
    
    stale_orders = Order.objects.filter(
        status=OrderStatus.PENDING,
        created_at__lte=ten_minutes_ago
    )
    
    count = stale_orders.count()
    if count > 0:
        logger.info(f"Auto-cancelling {count} stale orders.")
        for order in stale_orders:
            order.status = OrderStatus.CANCELLED
            order.save()
            order.broadcast_status_update()
            
            refunded = _attempt_order_refund(order)
            PushNotificationService.notify_order_status(
                order.customer, 
                "REFUNDED" if refunded else "CANCELLED",
                order.id
            )
            
    return f"Cancelled {count} orders."

@shared_task
def auto_cancel_stale_order(order_id):
    """
    Task to cancel a specific order if it's still pending after X minutes.
    Used for immediate scheduling after checkout.
    """
    try:
        order = Order.objects.get(id=order_id, status=OrderStatus.PENDING)
        order.status = OrderStatus.CANCELLED
        order.save()
        order.broadcast_status_update()
        
        refunded = _attempt_order_refund(order)
        PushNotificationService.notify_order_status(
            order.customer,
            "REFUNDED" if refunded else "CANCELLED",
            order.id,
        )
        
        return f"Order {order_id} auto-cancelled."
    except Order.DoesNotExist:
        return f"Order {order_id} already processed or does not exist."
