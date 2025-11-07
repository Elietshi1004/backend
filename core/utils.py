import json
import requests
from datetime import datetime, timedelta
from django.utils import timezone
from .models import Subscription, PushSubscription, NotificationPref

# Limite OneSignal : 2000 external_user_ids par appel
ONESIGNAL_MAX_IDS_PER_REQUEST = 2000

def calculate_send_after_time(frequency):
    """
    Calcule la date/heure d'envoi selon la fréquence de notification.
    
    Args:
        frequency: 'immediate', 'daily', ou 'weekly'
    
    Returns:
        str: Date ISO 8601 pour send_after, ou None si immediate
    """
    now = timezone.now()
    
    if frequency == 'immediate':
        return None  # Envoi immédiat
    
    elif frequency == 'daily':
        # Demain à 12h00 (toujours le jour suivant, peu importe l'heure)
        tomorrow = now + timedelta(days=1)
        send_time = tomorrow.replace(hour=12, minute=0, second=0, microsecond=0)
        return send_time.isoformat()
    
    elif frequency == 'weekly':
        # Prochain samedi à 12h00
        current_weekday = now.weekday()  # 0=lundi, 5=samedi, 6=dimanche
        current_hour = now.hour
        
        # Si on est samedi avant 12h, envoyer aujourd'hui à 12h
        if current_weekday == 5 and current_hour < 12:
            send_time = now.replace(hour=12, minute=0, second=0, microsecond=0)
        else:
            # Sinon, calculer le prochain samedi
            days_until_saturday = (5 - current_weekday) % 7
            if days_until_saturday == 0:
                # Si on est samedi après 12h ou dimanche, envoyer samedi prochain
                days_until_saturday = 7
            
            send_time = now + timedelta(days=days_until_saturday)
            send_time = send_time.replace(hour=12, minute=0, second=0, microsecond=0)
        
        return send_time.isoformat()
    
    return None


def send_notification_batch(external_ids, send_after, news, headers, batch_num, total_batches):
    """
    Envoie un batch de notifications à OneSignal.
    
    Returns:
        tuple: (success_count, error_count)
    """
    if not external_ids:
        return 0, 0
    
    # Préparer le contenu bilingue (requis par OneSignal)
    news_title = news.title_final or news.title_draft or "Nouvelle actualité"
    
    payload = {
        "app_id": "c2db50d7-c369-4be9-81f1-29f4455c26fb",  
        "include_external_user_ids": external_ids,
        "headings": {
            "en": "New validated news",
            "fr": "Nouvelle actualité validée"
        },
        "contents": {
            "en": news_title,
            "fr": news_title
        },
    }
    
    # Ajouter send_after si programmé
    if send_after:
        payload["send_after"] = send_after
    
    try:
        response = requests.post(
            "https://api.onesignal.com/notifications",
            data=json.dumps(payload),
            headers=headers,
            timeout=30
        )
        
        if response.status_code == 200:
            timing_info = f"programmé pour {send_after}" if send_after else "immédiat"
            print(f"✅ Batch {batch_num}/{total_batches} envoyé ({len(external_ids)} utilisateurs, {timing_info})")
            return len(external_ids), 0
        else:
            print(f"❌ Erreur batch {batch_num}/{total_batches} ({response.status_code}): {response.text[:200]}")
            return 0, len(external_ids)
            
    except requests.exceptions.Timeout:
        print(f"⏱️ Timeout batch {batch_num}/{total_batches} ({len(external_ids)} utilisateurs)")
        return 0, len(external_ids)
    except Exception as e:
        print(f"⚠️ Erreur batch {batch_num}/{total_batches}: {e}")
        return 0, len(external_ids)


def send_news_notification(news):
    """
    Envoie une notification OneSignal à tous les utilisateurs abonnés
    au programme de la news validée, en respectant leurs préférences.
    
    - Immediate : envoi immédiat
    - Daily : envoi programmé pour demain à 12h00
    - Weekly : envoi programmé pour le prochain samedi à 12h00
    - push_enabled=False : pas d'envoi
    """
    # Récupérer les utilisateurs abonnés au programme
    user_ids = Subscription.objects.filter(program=news.program).values_list('user_id', flat=True)
    
    if not user_ids:
        print("ℹ️ Aucun utilisateur abonné à ce programme")
        return
    
    # Récupérer les préférences de notification et push subscriptions
    prefs = NotificationPref.objects.filter(
        user_id__in=user_ids,
        push_enabled=True  # Seulement ceux qui ont activé les notifications push
    ).select_related('user')
    
    # Récupérer les external_user_ids pour ces utilisateurs
    push_subscriptions = PushSubscription.objects.filter(
        user_id__in=[pref.user_id for pref in prefs]
    ).select_related('user')
    
    # Créer un mapping user_id -> external_user_id
    user_to_external = {
        sub.user_id: sub.external_user_id 
        for sub in push_subscriptions
    }
    
    # Créer un mapping user_id -> frequency
    user_to_frequency = {
        pref.user_id: pref.frequency 
        for pref in prefs
    }
    
    # Grouper les external_ids par fréquence
    grouped_by_frequency = {
        'immediate': [],
        'daily': [],
        'weekly': []
    }
    
    for user_id, frequency in user_to_frequency.items():
        external_id = user_to_external.get(user_id)
        if external_id:
            grouped_by_frequency[frequency].append(external_id)
    
    headers = {
        "Authorization": "Key os_v2_app_ylnvbv6dnff6taprfh2ekxbg7ngb3ihhyf7ubv5fly6xkadme4errldtej2kd7otllb4h7qm2essieff5c3fd3xieznxi2eir2adlzy",  
        "Content-Type": "application/json",
    }
    
    total_success = 0
    total_errors = 0
    
    # Traiter chaque groupe de fréquence
    for frequency, external_ids in grouped_by_frequency.items():
        if not external_ids:
            continue
        
        send_after = calculate_send_after_time(frequency)
        timing_desc = "immédiat" if not send_after else f"programmé pour {send_after}"
        
        print(f"📬 Envoi {frequency}: {len(external_ids)} utilisateurs ({timing_desc})...")
        
        # Diviser en batches si nécessaire
        batches = [
            external_ids[i:i + ONESIGNAL_MAX_IDS_PER_REQUEST]
            for i in range(0, len(external_ids), ONESIGNAL_MAX_IDS_PER_REQUEST)
        ]
        
        for batch_num, batch_ids in enumerate(batches, 1):
            success, errors = send_notification_batch(
                batch_ids, send_after, news, headers, 
                batch_num, len(batches)
            )
            total_success += success
            total_errors += errors
    
    # Compter ceux qui ont désactivé les notifications
    disabled_count = len(user_ids) - len(user_to_frequency)
    
    print(f"📊 Résumé final:")
    print(f"   ✅ {total_success} notifications envoyées/programmées")
    print(f"   ❌ {total_errors} échecs")
    print(f"   🚫 {disabled_count} utilisateurs avec push désactivé")
    print(f"   📈 Total: {len(user_ids)} utilisateurs abonnés")
