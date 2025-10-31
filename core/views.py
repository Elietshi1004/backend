from django.shortcuts import render
from rest_framework import viewsets
from django.contrib.auth.models import User
from .models import *
from .serializers import *
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from .models import Role, NotificationPref
from rest_framework import status
from django.contrib.auth.models import User
from rest_framework_simplejwt.tokens import RefreshToken
from .models import UserRole
from .serializers import RoleSerializer
from .serializers import UserRoleSerializer
from rest_framework import filters
from rest_framework.decorators import action
@api_view(['POST'])
@permission_classes([AllowAny])  # accessible sans login
def signup(request):
    try:
        username = request.data.get('username')
        email = request.data.get('email')
        password = request.data.get('password')
        first_name = request.data.get('first_name', '')
        last_name = request.data.get('last_name', '')

        # Vérification des champs
        if not username or not password:
            return Response({"error": "Username et mot de passe requis."}, status=400)

        if User.objects.filter(username=username).exists():
            return Response({"error": "Ce nom d'utilisateur existe déjà."}, status=400)

        if email and User.objects.filter(email=email).exists():
            return Response({"error": "Cet email est déjà utilisé."}, status=400)

        # Création de l'utilisateur
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name
        )

        # Attribution du rôle par défaut : Étudiant (ou création s’il n’existe pas)
        role, created = Role.objects.get_or_create(name='Étudiant', defaults={'description': 'Utilisateur standard'})
        from .models import UserRole
        UserRole.objects.create(user=user, role=role)

        # Préférences de notification par défaut
        NotificationPref.objects.create(user=user)

        token = RefreshToken.for_user(user)
        return Response({
            "message": "Utilisateur créé avec succès.",
            "username": user.username,
            "email": user.email,
            "access": str(token.access_token),
            "refresh": str(token)
        }, status=status.HTTP_201_CREATED)

    except Exception as e:
        return Response({"error": str(e)}, status=500)


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer

class RoleViewSet(viewsets.ModelViewSet):
    queryset = Role.objects.all()
    serializer_class = RoleSerializer

class ProgramViewSet(viewsets.ModelViewSet):
    queryset = Program.objects.all()
    serializer_class = ProgramSerializer

class SubscriptionViewSet(viewsets.ModelViewSet):
    queryset = Subscription.objects.all()
    serializer_class = SubscriptionSerializer

class NewsViewSet(viewsets.ModelViewSet):
    queryset = News.objects.all().order_by('-created_at')
    serializer_class = NewsSerializer
    # 🔍 Activer la recherche et le tri
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['title_draft', 'title_final', 'content_draft', 'content_final', 'program__name']
    ordering_fields = ['created_at', 'publish_date_effective', 'importance']
    ordering = ['-created_at']
    # 🟡 Route personnalisée pour les news non modérées
    @action(detail=False, methods=['get'], url_path='pending')
    def pending_news(self, request):
        pending = News.objects.filter(moderator_approved=False)
        serializer = self.get_serializer(pending, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
        
     # 🟢 Route : news approuvées
    @action(detail=False, methods=['get'], url_path='approved')
    def approved_news(self, request):
        approved = News.objects.filter(moderator_approved=True)
        serializer = self.get_serializer(approved, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    # 🔴 Route : news refusées ou invalidées
    @action(detail=False, methods=['get'], url_path='rejected')
    def rejected_news(self, request):
        rejected = News.objects.filter(moderator_approved=False)
        serializer = self.get_serializer(rejected, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


    def get_queryset(self):
        queryset = super().get_queryset()
        program_id = self.request.query_params.get('program_id')
        author_id = self.request.query_params.get('author_id')
        importance = self.request.query_params.get('importance')

        if program_id:
            queryset = queryset.filter(program_id=program_id)
        if author_id:
            queryset = queryset.filter(author_id=author_id)
        if importance:
            queryset = queryset.filter(importance=importance)

        return queryset

class ModerationViewSet(viewsets.ModelViewSet):
    queryset = Moderation.objects.all()
    serializer_class = ModerationSerializer

class AttachmentViewSet(viewsets.ModelViewSet):
    queryset = Attachment.objects.all()
    serializer_class = AttachmentSerializer

class PublicationLogViewSet(viewsets.ModelViewSet):
    queryset = PublicationLog.objects.all()
    serializer_class = PublicationLogSerializer

class NotificationPrefViewSet(viewsets.ModelViewSet):
    queryset = NotificationPref.objects.all()
    serializer_class = NotificationPrefSerializer
    def get_queryset(self):
        queryset = super().get_queryset()
        user_id = self.request.query_params.get('user_id')
        if user_id:
            queryset = queryset.filter(user_id=user_id)
        return queryset

class UserRoleViewSet(viewsets.ModelViewSet):
    queryset = UserRole.objects.all()
    serializer_class = UserRoleSerializer

# Create your views here.
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def current_user(request):
    user = request.user
    # Récupérer les rôles associés à ce user
    user_roles = UserRole.objects.filter(user=user).select_related('role')
    roles_data = [RoleSerializer(ur.role).data for ur in user_roles]

    return Response({
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "roles": roles_data
    })