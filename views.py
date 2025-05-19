from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.core.files.storage import default_storage
from .models import UserProfile
import google.generativeai as genai
from django.conf import settings
from django.http import JsonResponse
import json
from .models import ChatMessage,UserProfile
from PIL import Image
import os
from datetime import datetime

# Configure Gemini API
genai.configure(api_key=settings.GOOGLE_GEMINI_API_KEY)
text_model = genai.GenerativeModel("gemini-2.0-flash")
vision_model = genai.GenerativeModel("gemini-2.0-flash")

# Function to process text input
def chat_with_gemini(user_input):
    system_prompt = (
        "I am a health and wellness chatbot. I only answer health-related queries        	like "
        "diet, food, BMI, exercise, medicines, lab reports, and prescriptions. "
        "I will answer the questions related to my capabilities as a health and    wellness chatbot professionally and elegantly."
        "For other topics, I respond: 'Sorry, out of my domain.'"
        "For images uploaded other than diet, food, BMI, exercise, medicines, lab reports, and prescriptions,I respond:'please upload proper image'"
    	)
    response = text_model.generate_content(system_prompt + "\nUser: " + user_input)
    return response.text

# Function to analyze an image
def analyze_image(image_path, question):
    
    img = Image.open(image_path)
    response = vision_model.generate_content(img)
    return response.text

def is_health_related(image_file):
    prompt = (
        "Is this image related to diet, food, BMI, exercise, medicines, lab reports, or prescriptions? "
        "Just answer with yes or no."
    )
    try:
        image = Image.open(image_file)
        response = vision_model.generate_content([prompt, image])
        return "yes" in response.text.lower()
    except Exception as e:
        print("Error processing image:", e)
        return False


@login_required
def chatbot_view(request):
    if request.method == "POST":
        text = request.POST.get("text", "").strip()
        image = request.FILES.get("image", None)
        chat_message = None
        system_prompt = (
        "I am a health and wellness chatbot. I only answer health-related queries        	like "
        "diet, food, BMI, exercise, medicines, lab reports, and prescriptions. "
        "I will answer the questions related to my capabilities as a health and    wellness chatbot professionally and elegantly."
        "For other topics, I respond: 'Sorry, out of my domain.'"
        "For images uploaded other than diet, food, BMI, exercise, medicines, lab reports, and prescriptions,I respond:'please upload proper image'"
    	)
	
        try:
            if image:
                if not is_health_related(image):
                    return JsonResponse({"response": "please upload proper image"})
                
                # Save image to DB
                chat_message = ChatMessage.objects.create(text=text or "Image input", image=image)
                image_path = chat_message.image.path

                # Prompt setup
                full_prompt = (
                    f"{system_prompt}\n\nUser: {text}"
                    if text else
                    f"{system_prompt}\n\nPlease analyze this image. If it's not health-related, reply: 'Sorry, out of my domain.'"
                )
                response_text = analyze_image(image_path, full_prompt)

            elif text:
                chat_message = ChatMessage.objects.create(text=text)
                response_text = chat_with_gemini(f"{system_prompt}\nUser: {text}")

            else:
                return JsonResponse({"message": "Please enter a valid question or upload an image."})

            return JsonResponse({
                "message": response_text,
                "image_url": chat_message.image.url if image else None
            })

        except Exception as e:
            return JsonResponse({"message": f"Error processing request: {str(e)}"})

    # For GET request
    messages = ChatMessage.objects.all().order_by("-timestamp")
    first_name = request.user.first_name or "there"
    return render(request, 'chatbot.html', {"messages": messages, "first_name": first_name})
    profile = UserProfile.objects.get(user=request.user)
    # Calculate age
    if profile.dob:
        today = datetime.today()
        age = today.year - profile.dob.year - (
            (today.month, today.day) < (profile.dob.month, profile.dob.day)
        )
    else:
        age = "N/A"

    context = {
        'user': {
            'first_name': profile.first_name,
            'email': profile.user.email,
            'dob': profile.dob,
            'profile_photo': profile.profile_photo,
            'age': age,
        }
    }
    return render(request, 'chatbot.html', context)
    

    
def new_chat(request):
    request.session['chat_history'] = []
    return JsonResponse({'status': 'cleared'})



def auth_page(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')

        # Check if it's a login form or profile creation (based on fields submitted)
        if 'first_name' in request.POST:
            # Profile Creation
            first_name = request.POST.get('first_name')
            last_name = request.POST.get('last_name', '')
            dob = request.POST.get('dob', '')
            profile_photo = request.FILES.get('profile_photo')

            if User.objects.filter(username=email).exists():
                return render(request, 'auth_page.html', {'error': 'Email already registered'})

            user = User.objects.create_user(username=email, email=email, password=password,
                                            first_name=first_name, last_name=last_name)
            user.save()

            # Save profile photo if needed (this is just an example)
            if profile_photo:
                default_storage.save(f"profile_photos/{email}_{profile_photo.name}", profile_photo)

            # Auto login after registration
            user = authenticate(request, username=email, password=password)
            if user:
                login(request, user)
                return redirect('chatbot')

        else:
            # Login
            user = authenticate(request, username=email, password=password)
            if user:
                login(request, user)
                return redirect('chatbot')
            else:
                return render(request, 'auth_page.html', {'error': 'Invalid credentials'})

    return render(request, 'auth_page.html')

def profile_view(request):
    if request.method == 'POST':
        first_name = request.POST['first_name']
        dob = request.POST['dob']
        profile_photo = request.FILES.get('profile_photo')

        profile = UserProfile.objects.create(
            user=request.user,
            first_name=first_name,
            dob=dob,
            profile_photo=profile_photo
        )
        return redirect('chatbot')

    return render(request, 'profile.html')

def about_chatbot(request):
	return redirect('auth_page')

def about_view(request):
    return render(request, 'about.html')
