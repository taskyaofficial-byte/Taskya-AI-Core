from enum import Enum
class Risk(str,Enum):
    LOW="low"; APPROVAL="approval_required"
def classify(text):
    t=text.lower()
    words=("pay ","purchase","buy ","send email","submit","publish","book ","transfer ","delete ","destroy ")
    return Risk.APPROVAL if any(x in t for x in words) else Risk.LOW
