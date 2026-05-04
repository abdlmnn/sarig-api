Building a food delivery platform on Django & DRF is a powerhouse choice. Django’s "batteries-included" philosophy means you get a secure admin panel (crucial for managing restaurants) and robust data handling right out of the box.

Here is your Technical Roadmap to pivot Sarig from a job board to a food delivery platform.

🛠️ The "Sarig App" Build Plan (MVP Phase)
Phase 1: The Merchant & Menu Models
Since you already updated your User and UserProfile, your next step is to create the entities that sell the food.

Store Model: Connects to a User (the Merchant owner). Includes store name, logo, "open/closed" toggle, and their specific Barangay.

Category Model: (e.g., Beverages, Rice Meals, Snacks).

Product Model: The actual food items. Link these to a Store and a Category.

Phase 2: The Order & Cart Logic
This is the heart of the app. You need to track a "Basket" that turns into an "Order."

Order Model: This tracks the lifecycle of a meal.

Statuses: PENDING -> ACCEPTED -> PREPARING -> OUT_FOR_DELIVERY -> DELIVERED -> CANCELLED.

OrderItem Model: A "Through" table that connects an Order to Products (including quantity and price at the time of purchase).

Phase 3: The Dispatch System (The "Rider" Side)
In Marawi, location is key. Your backend needs to:

Identify orders that are READY_FOR_PICKUP.

Notify nearby RIDER profiles.

Allow a Rider to "Claim" an order.

Phase 4: Payments & Real-Time Updates
Localization: Since GCash and Maya are king in the PH, look into Xendit or PayMaya API for DRF. Start with Cash on Delivery (COD) as your default—it’s the fastest way to launch.

WebSockets: Use Django Channels for real-time tracking so the customer sees the status change without refreshing.

💻 Start Here: The Store & Menu Models
Copy this into your models.py to get the Merchant side started.

Python
class Store(models.Model):
    owner = models.OneToOneField(User, on_delete=models.CASCADE, limit_choices_to={'profile__role': 2})
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    logo = models.ImageField(upload_to='store_logos/', null=True, blank=True)
    is_active = models.BooleanField(default=True) # "Open" or "Closed"
    barangay = models.ForeignKey(Barangay, on_delete=models.PROTECT)

    def __str__(self):
        return self.name

class Category(models.Model):
    name = models.CharField(max_length=100)
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='categories')

    class Meta:
        verbose_name_plural = "Categories"

class Product(models.Model):
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='products')
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='products')
    name = models.CharField(max_length=255)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    image = models.ImageField(upload_to='food_items/', null=True, blank=True)
    is_available = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name} - {self.store.name}"
🚀 Your "Build" Checklist for this week:
[ ] Run Migrations: Apply the new Store, Category, and Product models.

[ ] Register in Admin: Add these to admin.py. This lets you manually add the first 3 cafes in Marawi via the Django Admin panel just to see them in your database.

[ ] Create Serializers: In DRF, create a StoreDetailSerializer that nests the Category and Product data.

[ ] Endpoint Check: Try to hit GET /api/stores/ and see if you get a list of restaurants and their menus.

Ready to dive into the Order logic, or do you want to finish setting up these Store endpoints first?
