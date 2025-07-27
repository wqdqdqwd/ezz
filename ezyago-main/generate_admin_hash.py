#!/usr/bin/env python3
"""
Admin şifre hash'i oluşturmak için kullanın
Kullanım: python generate_admin_hash.py
"""

from passlib.context import CryptContext
import getpass

def generate_admin_hash():
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    
    print("🔐 Admin Şifre Hash Oluşturucu")
    print("=" * 40)
    
    password = getpass.getpass("Yeni admin şifresini girin: ")
    confirm_password = getpass.getpass("Şifreyi tekrar girin: ")
    
    if password != confirm_password:
        print("❌ Şifreler eşleşmiyor!")
        return
    
    if len(password) < 8:
        print("❌ Şifre en az 8 karakter olmalı!")
        return
    
    # Hash oluştur
    password_hash = pwd_context.hash(password)
    
    print("\n✅ Şifre hash'i oluşturuldu!")
    print("=" * 40)
    print(f"ADMIN_PASSWORD_HASH={password_hash}")
    print("=" * 40)
    print("\n📝 Bu hash'i .env dosyanıza ekleyin:")
    print(f"ADMIN_PASSWORD_HASH={password_hash}")
    print("\n⚠️  Güvenlik için ADMIN_PASSWORD satırını silin!")

if __name__ == "__main__":
    generate_admin_hash()