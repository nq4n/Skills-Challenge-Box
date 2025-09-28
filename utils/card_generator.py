import random
import string
from datetime import datetime

def generate_serial(skill_code, batch_num=1):
    """
    Generate a unique serial number for a skill card.
    Format: SCB-XXX-000-YYYY
    - SCB: Skills Challenge Box prefix
    - XXX: First 3 letters of skill code (e.g., COM for communication)
    - 000: Batch number (001-999)
    - YYYY: Random alphanumeric string
    """
    # Get first 3 letters of skill code, uppercase
    skill_prefix = skill_code[:3].upper()
    
    # Format batch number with leading zeros
    batch = str(batch_num).zfill(3)
    
    # Generate random string of 4 characters (letters and numbers)
    chars = string.ascii_uppercase + string.digits
    random_suffix = ''.join(random.choices(chars, k=4))
    
    # Combine all parts
    serial = f"SCB-{skill_prefix}-{batch}-{random_suffix}"
    
    return serial

def create_card(skill_name, serial=None):
    """
    Create a new card entry with generated serial number if not provided.
    """
    if not serial:
        serial = generate_serial(skill_name)
    
    return {
        "id": serial,
        "skill_name": skill_name,
        "created_at": datetime.now().strftime("%Y-%m-%d"),
        "holder": None,
        "scanned_at": None
    }

def batch_generate_cards(skill_name, count=5):
    """
    Generate multiple cards for a skill.
    """
    cards = []
    for i in range(count):
        serial = generate_serial(skill_name, i + 1)
        cards.append(create_card(skill_name, serial))
    return cards