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
from .models import PushSubscription, NewsView
from .serializers import PushSubscriptionSerializer, NewsViewSerializer
import requests, json
from .utils import send_news_notification


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
    #  Route personnalisée pour les news non modérées
    @action(detail=False, methods=['get'], url_path='pending')
    def pending_news(self, request):
        pending = News.objects.filter(moderator_approved=False)
        serializer = self.get_serializer(pending, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
        
     #  Route : news approuvées
    @action(detail=False, methods=['get'], url_path='approved')
    def approved_news(self, request):
        approved = News.objects.filter(moderator_approved=True)
        serializer = self.get_serializer(approved, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    #  Route : news refusées ou invalidées
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


class PushSubscriptionViewSet(viewsets.ModelViewSet):
    queryset = PushSubscription.objects.all()
    serializer_class = PushSubscriptionSerializer

class NewsViewViewSet(viewsets.ModelViewSet):
    queryset = NewsView.objects.all()
    serializer_class = NewsViewSerializer

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



# ✅ Enregistrement du external_user_id OneSignal
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def register_push_subscription(request):
    user = request.user
    external_user_id = request.data.get('external_user_id')
    device_token = request.data.get('device_token')

    if not external_user_id:
        return Response({'error': 'external_user_id requis'}, status=400)

    sub, created = PushSubscription.objects.update_or_create(
        user=user,
        defaults={'external_user_id': external_user_id, 'device_token': device_token}
    )

    return Response({'success': True, 'created': created, 'external_user_id': sub.external_user_id})


# ✅ Marquer une news comme vue
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_news_viewed(request, news_id):
    user = request.user
    from .models import News

    try:
        news = News.objects.get(id=news_id)
    except News.DoesNotExist:
        return Response({'error': 'News not found'}, status=404)

    view, created = NewsView.objects.get_or_create(user=user, news=news)
    return Response({'viewed': True, 'created': created})


# ✅ Lister les news non encore vues selon abonnements
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def unread_news(request):
    user = request.user
    from .models import News, Subscription

    subscribed_programs = Subscription.objects.filter(user=user).values_list('program_id', flat=True)
    seen_news = NewsView.objects.filter(user=user).values_list('news_id', flat=True)

    unread = News.objects.filter(
        program_id__in=subscribed_programs,
        moderator_approved=True
    ).exclude(id__in=seen_news)

    serializer = NewsSerializer(unread, many=True)
    return Response(serializer.data)


@api_view(['PATCH', 'PUT'])
@permission_classes([IsAuthenticated])
def update_news(request, pk):
    """
    Permet de mettre à jour une news (modérateurs/admins),
    et déclenche une notification push OneSignal si la news
    vient d'être validée (moderator_approved=True).
    """
    try:
        news = News.objects.get(pk=pk)
    except News.DoesNotExist:
        return Response({'error': 'News introuvable'}, status=404)

    old_state = news.moderator_approved  # on garde l'ancien état
    serializer = NewsSerializer(news, data=request.data, partial=True)

    if serializer.is_valid():
        serializer.save()

        # Si la news vient d'être validée, envoyer la notification
        if not old_state and serializer.data.get('moderator_approved'):
            send_news_notification(news)

        return Response(serializer.data)
    else:
        return Response(serializer.errors, status=400)

# ✅ Récupérer le nombre de vues par news
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def news_views_count(request, news_id=None):
    """
    - Si news_id est fourni : retourne le nombre de vues pour cette news.
    - Sinon : retourne la liste des news avec leur nombre total de vues.
    """
    from .models import News, NewsView

    if news_id:
        try:
            news = News.objects.get(id=news_id)
        except News.DoesNotExist:
            return Response({'error': 'News introuvable'}, status=404)

        count = NewsView.objects.filter(news=news).count()
        viewers = NewsView.objects.filter(news=news).select_related('user')
        viewers_list = [
            {
                'id': v.user.id,
                'username': v.user.username,
                'email': v.user.email
            }
            for v in viewers
        ]

        return Response({
            'news_id': news.id,
            'title_final': news.title_final or news.title_draft,
            'views_count': count,
            'viewers': viewers_list
        })

    else:
        # Récupère toutes les news avec leur nombre total de vues
        from django.db.models import Count
        stats = (
            News.objects.annotate(views_count=Count('views'))
            .values('id', 'title_final', 'views_count')
            .order_by('-views_count')
        )
        return Response(list(stats))
