from django.db import models
from django.contrib.auth.models import User

# --- Programme d'étude ---
class Program(models.Model):
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.name

# --- Rôles utilisateur ---
class Role(models.Model):
    name = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name

# --- Liaison utilisateur ↔ rôle ---
class UserRole(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    role = models.ForeignKey(Role, on_delete=models.CASCADE)

    class Meta:
        unique_together = ('user', 'role')

    def __str__(self):
        return f"{self.user.username} - {self.role.name}"

# --- Abonnement utilisateur ↔ programme ---
class Subscription(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    program = models.ForeignKey(Program, on_delete=models.CASCADE)
    subscribed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'program')

    def __str__(self):
        return f"{self.user.username} → {self.program.name}"

# --- Actualités ---
class News(models.Model):
    IMPORTANCE_CHOICES = [
        ('faible', 'Faible'),
        ('moyenne', 'Moyenne'),
        ('importante', 'Importante'),
        ('urgente', 'Urgente'),
    ]

    author = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='news_authored')
    program = models.ForeignKey(Program, on_delete=models.SET_NULL, null=True)
    title_draft = models.CharField(max_length=255, blank=True)
    content_draft = models.TextField(blank=True)
    title_final = models.CharField(max_length=255, blank=True)
    content_final = models.TextField(blank=True)
    importance = models.CharField(max_length=10, choices=IMPORTANCE_CHOICES, default='moyenne')
    moderator_approved = models.BooleanField(default=False)
    moderator = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='news_moderated')
    written_at = models.DateTimeField(auto_now_add=True)
    moderated_at = models.DateTimeField(null=True, blank=True)
    publish_date_requested = models.DateField(null=True, blank=True)
    publish_date_effective = models.DateField(null=True, blank=True)
    invalidated = models.BooleanField(default=False)
    invalidated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='news_invalidated')
    invalidation_reason = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title_final or self.title_draft

# --- Modération ---
class Moderation(models.Model):
    news = models.ForeignKey(News, on_delete=models.CASCADE, related_name='moderations')
    moderator = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    approved = models.BooleanField()
    comment = models.TextField(blank=True)
    moderated_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.moderator} - {self.news.title_final}"

# --- Pièces jointes ---
class Attachment(models.Model):
    news = models.ForeignKey(News, on_delete=models.CASCADE, related_name='attachments')
    file = models.FileField(upload_to='attachments/')  # 🔹 stocke le fichier réel
    mime = models.CharField(max_length=100, blank=True)
    filesize = models.IntegerField(default=0)

    def save(self, *args, **kwargs):
        if self.file:
            self.filesize = self.file.size
            self.mime = self.file.file.content_type if hasattr(self.file, 'file') else ''
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.file.name}"


class PublicationLog(models.Model):
    news = models.ForeignKey('News', on_delete=models.CASCADE, related_name='logs')
    scheduled_at = models.DateTimeField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    channel = models.CharField(max_length=50)
    sent_count = models.IntegerField(default=0)

    def __str__(self):
        return f"Log: {self.news.title_final} ({self.channel})"

class NotificationPref(models.Model):
    FREQUENCY_CHOICES = [
        ('immediate', 'Immédiate'),
        ('daily', 'Quotidienne'),
        ('weekly', 'Hebdomadaire'),
    ]
    user = models.OneToOneField('auth.User', on_delete=models.CASCADE)
    frequency = models.CharField(max_length=10, choices=FREQUENCY_CHOICES, default='immediate')
    push_enabled = models.BooleanField(default=True)
    email_enabled = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Prefs({self.user.username})"
