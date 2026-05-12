from rest_framework import serializers
from .models import ChatMessage, RideChatMessage

class ChatMessageSerializer(serializers.ModelSerializer):
    sender_name = serializers.ReadOnlyField(source="sender.username")
    
    class Meta:
        model = ChatMessage
        fields = ["id", "sender", "sender_name", "content", "created_at"]


class RideChatMessageSerializer(serializers.ModelSerializer):
    sender_name = serializers.ReadOnlyField(source="sender.username")

    class Meta:
        model = RideChatMessage
        fields = ["id", "sender", "sender_name", "content", "created_at"]
