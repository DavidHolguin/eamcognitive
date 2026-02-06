import os
import sys
import base64
from dotenv import load_dotenv
import jwt
from supabase import create_client

# Cargar .env
load_dotenv()

print("\n🔍 --- EAM COGNITIVE: JWT DEBUGGER V2 --- 🔍")
print("Diagnóstico avanzado con soporte Base64.")

# 1. Verificar Variables
secret = os.getenv("SUPABASE_JWT_SECRET")
# Compatibility with user input
if not secret:
    secret = os.getenv("JWT_SECRET")

print(f"\n1. Configuración:"
      f"\n   - SUPABASE_JWT_SECRET: {'✅ Configurado' if secret else '❌ FALTANTE'}")

if not secret:
    print("\n❌ ERROR FATAL: Falta el secreto en .env (SUPABASE_JWT_SECRET o JWT_SECRET)")
    sys.exit(1)

# 2. Solicitar Token
token = input("\n📋 Pega tu token JWT aquí (sin 'Bearer '): ").strip()
if token.startswith("Bearer "):
    token = token[7:]

# 3. Pruebas Local
print("\n🔑 2. Prueba Validación Local (PyJWT):")

# A. Intento Directo (Raw String)
print("   👉 A. Intentando con secreto como STRING RAW...")
try:
    jwt.decode(
        token, 
        secret, 
        algorithms=["HS256"], 
        audience="authenticated",
        options={"verify_exp": True}
    )
    print("      ✅ ÉXITO: El secreto se usa tal cual (Raw String).")
except jwt.InvalidSignatureError:
    print("      ❌ Fallo Firma: No es string raw.")
except Exception as e:
    print(f"      ❌ Error: {str(e)}")

# B. Intento Base64 Decode
print("   👉 B. Intentando con secreto DECODIFICADO (Base64)...")
try:
    decoded_secret = base64.b64decode(secret)
    jwt.decode(
        token, 
        decoded_secret, 
        algorithms=["HS256"], 
        audience="authenticated",
        options={"verify_exp": True}
    )
    print("      ✅ ÉXITO: El secreto requiere Base64 Decode.")
except Exception as e:
    print(f"      ❌ Error: {str(e)}")

print("\n---------------------------------------------------")
