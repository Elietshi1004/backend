from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import *
from .views import signup

router = DefaultRouter()
router.register('users', UserViewSet)
router.register('roles', RoleViewSet)
router.register('userroles', UserRoleViewSet)
router.register('programs', ProgramViewSet)
router.register('subscriptions', SubscriptionViewSet)
router.register('news', NewsViewSet)
router.register('moderations', ModerationViewSet)
router.register('attachments', AttachmentViewSet)
router.register('logs', PublicationLogViewSet)
router.register('notifications', NotificationPrefViewSet)
router.register('push_subscriptions', PushSubscriptionViewSet)
router.register('news_views', NewsViewViewSet)

# Routes personnalisées AVANT le router pour éviter les conflits
urlpatterns = [
    # Routes news spécifiques (doivent être avant le router)
    path('news/unread/', unread_news, name='unread_news'),
    path('news/<int:news_id>/view/', mark_news_viewed, name='mark_news_viewed'),
    path('news/<int:pk>/update/', update_news, name='update_news'),
    path('news/views/', news_views_count, name='all_news_views_count'),
    path('news/<int:news_id>/views/', news_views_count, name='single_news_views_count'),
    # Autres routes personnalisées
    path('me/', current_user),
    path('signup/', signup), 
    path('register_push/', register_push_subscription, name='register_push'),
    # Router URLs (doit être en dernier)
    path('', include(router.urls)),
]
