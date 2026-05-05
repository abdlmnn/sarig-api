from django.db import transaction
from apps.orders.models import Order
from apps.catalog.models import Product

class InventoryService:

    @staticmethod
    @transaction.atomic # The all-or-nothing database lock
    def deduct_stock_for_order(order_id):
        try:
            # Fetch the order and pre-fetch the items to save database hits
            order = Order.objects.prefetch_related('items__product').get(id=order_id)

            for item in order.items.all():
                product = item.product

                # We only care if the vendor actually tracks stock for this item
                if product.track_inventory:

                    # THE MAGIC LINE: select_for_update()
                    # This physically locks this exact product in the PostgreSQL database.
                    # If another customer is trying to buy it right now, they are forced
                    # to wait in line for a few milliseconds until this lock is released.
                    locked_product = Product.objects.select_for_update().get(id=product.id)

                    if locked_product.stock_quantity >= item.quantity:
                        locked_product.stock_quantity -= item.quantity

                        # Auto-disable the product if it hits absolute zero!
                        if locked_product.stock_quantity == 0:
                            locked_product.is_available = False

                        locked_product.save()
                    else:
                        # EDGE CASE: They paid, but someone else bought the last item 1 second ago.
                        # We raise an error so the Webhook knows to issue an automatic refund.
                        raise ValueError(f"Insufficient stock for {product.name}")

            return True, "Inventory successfully deducted."

        except Order.DoesNotExist:
            return False, "Order not found."
        except ValueError as e:
            # The stock ran out during the millisecond they were paying
            return False, str(e)
        except Exception as e:
            return False, "A system error occurred during inventory deduction."
