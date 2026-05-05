from celery import shared_task
from django.utils import timezone
from datetime import timedelta
from .models import Order, OrderStatus
import logging

logger = logging.getLogger(__name__)

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
            
            # TODO: Trigger automatic refund if paid via PayMongo
            from apps.users.notifications import PushNotificationService
            PushNotificationService.notify_order_status(
                order.customer, 
                "CANCELLED", 
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
        
        from apps.users.notifications import PushNotificationService
        PushNotificationService.notify_order_status(order.customer, "CANCELLED", order.id)
        
        return f"Order {order_id} auto-cancelled."
    except Order.DoesNotExist:
        return f"Order {order_id} already processed or does not exist."
