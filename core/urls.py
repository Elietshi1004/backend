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

urlpatterns = [
    path('', include(router.urls)),
    path('me/', current_user),
    path('signup/', signup), 
]
