"""Twilio WhatsApp webhook handler.                                                                                         
                                                                                                                              
Receives POST requests from Twilio, validates HMAC signature, and drives the                                                
Redis-backed conversation state machine through extraction → translation → TTS.                                             
                                                                                                                            
Integration: registered in main.py at POST /webhook/whatsapp.                                                               
Stub — implementation coming in Day 1 prototype.                                                                            
"""

from fastapi import APIRouter

router = APIRouter()