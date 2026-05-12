# Chat API

The Chat API provides order-bound, real-time messaging between Customers and Riders using Django Channels (WebSockets).

## WebSocket Connection
`ws/chat/<uuid:order_id>/`
- Connects to the `ChatConsumer`.
- **Security Check**: Verifies that the connected user is either the Customer who placed the order or the assigned Rider. Blocks all third-party access.
- **Lifecycle Check**: Chat automatically closes (rejects connection) if the order is `DELIVERED` or `CANCELLED`.
- **Broadcasts**: Saves the message to the DB and broadcasts to the group. Triggers a push notification to the recipient.

## REST Endpoints

### 1. Chat History & Contact Info
`GET /api/v1/chat/history/<uuid:order_id>/`
- Returns all past messages for a specific order.
- **In-App Calling Ready**: Automatically includes a `contact_info` object containing the `name` and `phone_number` of the person on the other end of the chat. This allows frontend developers to easily implement a "Direct Call" button inside the chat header.
- **Privacy Check**: Customers only see the Rider's phone number, and Riders only see the Customer's phone number.
- Requires same ownership checks as the WebSocket connection.
