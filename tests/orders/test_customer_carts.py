from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from apps.catalog.models import Category, Product, ProductType
from apps.orders.models import CustomerCart, CustomerCartItem
from apps.users.models import Role, User
from apps.vendors.models import BusinessVertical, Store


class CustomerCartApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        customer_role, _ = Role.objects.get_or_create(name="Customer")
        self.customer = User.objects.create_user(
            username="cart-customer",
            email="cart-customer@example.com",
            password="password123",
        )
        self.customer.roles.add(customer_role)
        owner = User.objects.create_user(
            username="cart-owner",
            email="cart-owner@example.com",
            password="password123",
        )
        vertical = BusinessVertical.objects.create(
            name="Cart Restaurant",
            slug="cart-restaurant",
        )
        self.store = Store.objects.create(
            owner=owner,
            vertical=vertical,
            name="Cart Store",
            latitude=Decimal("8.003400"),
            longitude=Decimal("124.283900"),
            street_address="Test Street",
            city="Marawi",
            is_open=True,
            is_active=True,
        )
        category = Category.objects.create(
            store=self.store,
            name="Meals",
            slug="meals",
        )
        self.product = Product.objects.create(
            category=category,
            name="Chicken Meal",
            price=Decimal("125.00"),
            product_type=ProductType.FOOD,
            is_available=True,
            is_active=True,
        )
        self.client.force_authenticate(self.customer)

    def test_customer_can_add_update_and_remove_cart_item(self):
        add = self.client.put(
            f"/api/v1/orders/carts/items/{self.product.id}/",
            {"quantity": 2},
            format="json",
        )

        self.assertEqual(add.status_code, 200)
        self.assertEqual(add.data[0]["items"][0]["quantity"], 2)
        self.assertEqual(add.data[0]["subtotal"], "250.00")

        update = self.client.put(
            f"/api/v1/orders/carts/items/{self.product.id}/",
            {"quantity": 3},
            format="json",
        )
        self.assertEqual(update.data[0]["items"][0]["quantity"], 3)

        remove = self.client.delete(
            f"/api/v1/orders/carts/items/{self.product.id}/"
        )
        self.assertEqual(remove.status_code, 200)
        self.assertEqual(remove.data, [])
        self.assertFalse(CustomerCart.objects.exists())

    def test_sync_is_idempotent_and_keeps_larger_server_quantity(self):
        payload = {
            "baskets": [
                {
                    "store_id": str(self.store.id),
                    "items": [
                        {
                            "product_id": str(self.product.id),
                            "quantity": 2,
                        }
                    ],
                }
            ]
        }

        first = self.client.post(
            "/api/v1/orders/carts/sync/",
            payload,
            format="json",
        )
        second = self.client.post(
            "/api/v1/orders/carts/sync/",
            payload,
            format="json",
        )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        item = CustomerCartItem.objects.get()
        self.assertEqual(item.quantity, 2)

    def test_non_customer_cannot_access_customer_carts(self):
        admin = User.objects.create_superuser(
            username="cart-admin",
            email="cart-admin@example.com",
            password="password123",
        )
        self.client.force_authenticate(admin)

        response = self.client.get("/api/v1/orders/carts/")

        self.assertEqual(response.status_code, 403)

    def test_replace_sync_updates_quantity_exactly(self):
        CustomerCartItem.objects.create(
            cart=CustomerCart.objects.create(
                customer=self.customer,
                store=self.store,
            ),
            product=self.product,
            quantity=4,
        )
        payload = {
            "mode": "REPLACE",
            "baskets": [
                {
                    "store_id": str(self.store.id),
                    "items": [
                        {
                            "product_id": str(self.product.id),
                            "quantity": 1,
                        }
                    ],
                }
            ],
        }

        response = self.client.post(
            "/api/v1/orders/carts/sync/",
            payload,
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(CustomerCartItem.objects.get().quantity, 1)

    def test_cart_rejects_closed_store(self):
        self.store.is_open = False
        self.store.save(update_fields=["is_open", "updated_at"])

        response = self.client.put(
            f"/api/v1/orders/carts/items/{self.product.id}/",
            {"quantity": 1},
            format="json",
        )

        self.assertEqual(response.status_code, 400)

    def test_invalid_replace_sync_does_not_delete_existing_cart(self):
        cart = CustomerCart.objects.create(
            customer=self.customer,
            store=self.store,
        )
        CustomerCartItem.objects.create(
            cart=cart,
            product=self.product,
            quantity=2,
        )

        response = self.client.post(
            "/api/v1/orders/carts/sync/",
            {
                "mode": "REPLACE",
                "baskets": [
                    {
                        "store_id": str(self.store.id),
                        "items": [
                            {
                                "product_id": "00000000-0000-0000-0000-000000000001",
                                "quantity": 1,
                            }
                        ],
                    }
                ],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertTrue(CustomerCartItem.objects.filter(cart=cart).exists())
