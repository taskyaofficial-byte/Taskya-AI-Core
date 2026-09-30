from enum import Enum
class Risk(str,Enum): LOW='low'; APPROVAL='approval_required'
SENSITIVE=('pay ','purchase','buy ','send email','send message','submit ','publish','book ','transfer ','delete ','destroy ','checkout','place order')
def classify(text):
 t=' '+text.lower().strip();return Risk.APPROVAL if any(x in t for x in SENSITIVE) else Risk.LOW
