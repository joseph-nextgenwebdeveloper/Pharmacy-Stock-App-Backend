from rest_framework import generics
from rest_framework.permissions import IsAuthenticated

from .models import GoodsReceived
from .serializers import GoodsReceivedSerializer


class GoodsReceivedListCreateView(generics.ListCreateAPIView):
    queryset = GoodsReceived.objects.all()
    serializer_class = GoodsReceivedSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save()



class GoodsReceivedDetailView(generics.RetrieveAPIView):
    queryset = GoodsReceived.objects.all()
    serializer_class = GoodsReceivedSerializer
    permission_classes = [IsAuthenticated]

