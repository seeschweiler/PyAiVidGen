import argparse
import os
import json
import requests
import shutil
from openai import OpenAI
import colorama
from colorama import Fore, Style
from dotenv import load_dotenv

colorama.init(autoreset=True)
load_dotenv()

openai_api_key = os.getenv("OPENAI_API_KEY")
if not openai_api_key:
    print("Error: OpenAI API key not found. Please check your .env file.")
    exit(1)

client = OpenAI(api_key=openai_api_key)

def print_green_bold(text):
    print(Fore.GREEN + Style.BRIGHT + text + Style.RESET_ALL)

def read_settings():
    try:
        with open('settings.json', 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        print("settings.json file not found.")
        return None

settings = read_settings()
if settings is None:
    exit(1)

def generate_text_with_openai():
    user_message = settings.get('user_message', '')
    try:
        response = client.chat.completions.create(model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a helpful assistant which is able to generate guided meditations as text."},
            {"role": "user", "content": user_message}
        ],
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Error while generating text with OpenAI: {e}")
        return None

def save_generated_text(text):
    text_output_file = settings.get('text_output_file', 'text_output.txt')
    with open(text_output_file, 'w') as file:
        file.write(text)

def ask_user_for_text_generation():
    response = input("Do you want to generate text? [Y/n]: ").strip().lower()
    return response in ['', 'y', 'yes']

def ask_user_for_text_to_speech_transformation():
    response = input("Do you want to proceed with Text-to-Speech transformation? [Y/n]: ").strip().lower()
    return response in ['', 'y', 'yes']

def perform_text_to_speech_transformation(text_file):
    try:
        with open(text_file, 'r') as file:
            text = file.read()
            
            mp3_output_file = text_file.replace('.txt', '.mp3')
            response = client.audio.speech.create(
                model="tts-1",
                voice="nova",
                speed=0.75,
                input=text
            )
            response.stream_to_file(mp3_output_file)
            print_green_bold(f"Text-to-Speech output written to file {mp3_output_file}.")

    except Exception as e:
        print(f"Error during Text-to-Speech transformation: {e}")

def ask_user_for_image_generation():
    response = input("Do you want to start the image generation process? [Y/n]: ").strip().lower()
    return response in ['', 'y', 'yes']

def generate_image_prompts(text, num_prompts):
    prompts = []
    try:
        for _ in range(num_prompts):
            response = client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant who is able to generate perfect DallE 3 image generation prompts. Those prompts should be perfect for generating images to accompany the spoken text in a video. Please only output the prompt for the text the user is providing. Please do not include any further instructions or explainations in your answer, only the prompt text."},
                    {"role": "user", "content": text}
                ],
                temperature=1.4
            )
            prompt = response.choices[0].message.content.strip()
            prompts.append(prompt)
    except Exception as e:
        print(f"Error while generating image prompts with OpenAI: {e}")
    
    return prompts

def generate_and_save_images(prompts, image_output_folder):
    # Empty the image output folder first
    empty_directory(image_output_folder)
   
    for i, prompt in enumerate(prompts, 1):
        try:
            response = client.images.generate(
                model="dall-e-3",
                prompt=prompt,
                size="1792x1024",
                quality="hd",
                n=1,
            )
            # Assuming the API returns the image URL
            image_url = response.data[0].url

            # Call download_image function
            image_file_path = os.path.join(image_output_folder, f"image_{i}.png")
            download_image(image_url, image_file_path)

            print_green_bold(f"Image {i} generated and saved in {image_output_folder}")

        except Exception as e:
            print(f"Error during image generation for prompt {i}: {e}")

def download_image(image_url, file_path):
    try:
        response = requests.get(image_url)
        response.raise_for_status()

        with open(file_path, 'wb') as file:
            file.write(response.content)

        print_green_bold(f"Image downloaded and saved to {file_path}")
    except requests.exceptions.RequestException as e:
        print(f"Error downloading image: {e}")

def empty_directory(folder_path):
    for item in os.listdir(folder_path):
        item_path = os.path.join(folder_path, item)
        if os.path.isfile(item_path):
            os.remove(item_path)
        elif os.path.isdir(item_path):
            shutil.rmtree(item_path)

def main(args):
    text_file_available = False
    mp3_file_exists = False
    text_output_file = args.text_file if args.text_file else settings.get('text_output_file', 'text_output.txt')

    if args.text_file:
        print_green_bold("Using provided text file.")
        text_file_available = True

        # Check if corresponding MP3 file exists
        mp3_output_file = args.text_file.replace('.txt', '.mp3')
        if os.path.exists(mp3_output_file):
            print_green_bold(f"Corresponding voice MP3 file found: {mp3_output_file}. It will be used.")
            mp3_file_exists = True
    else:
        if ask_user_for_text_generation():
            print_green_bold("Generating text using OpenAI.")
            generated_text = generate_text_with_openai()
            if generated_text:
                save_generated_text(generated_text)
                args.text_file = settings.get('text_output_file', 'text_output.txt')
                text_file_available = True
        else:
            print("Text generation skipped.")

    if text_file_available and not mp3_file_exists:
        if ask_user_for_text_to_speech_transformation():
            print_green_bold("Text-to-Speech transformation selected.")
            perform_text_to_speech_transformation(args.text_file)
        else:
            print("Text-to-Speech transformation skipped.")

    # Image output folder handling
    image_output_folder = args.image_output_folder if args.image_output_folder else settings.get('default_image_output_folder', 'image_output')
    print_green_bold(f"Images will be saved in the folder: {image_output_folder}")

    # Ensure the output folder exists
    os.makedirs(image_output_folder, exist_ok=True)

    # Ask user for image generation
    if ask_user_for_image_generation():
        print_green_bold("Image generation process selected.")

        # Read the maximum number of images from settings
        max_num_images = settings.get('max_num_images', 5)

        # Determine the actual number of images to generate
        num_images = min(args.num_images if args.num_images else settings.get('default_num_images', 5), max_num_images)
        
        # Read the text from the output file
        try:
            with open(text_output_file, 'r') as file:
                text_content = file.read()
        except FileNotFoundError:
            print(f"Error: Text output file {text_output_file} not found.")
            return

        image_prompts = generate_image_prompts(text_content, num_images)
        
        # Output image prompts array to the console
        print_green_bold("Generated Image Prompts:")
        for i, prompt in enumerate(image_prompts, 1):
            print(f"Prompt {i}: {prompt}")
        
                # Generate and save images
        generate_and_save_images(image_prompts, image_output_folder)
    else:
        print("Image generation process skipped.")

    # Rest of your main function logic

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='PyAIVidGen: A tool to generate YouTube videos using AI')

    parser.add_argument('-t', '--text-file', type=str, help='Path to the text file (txt) for voice conversion', required=False)
    parser.add_argument('-m', '--music-file', type=str, help='Path to the background music file (mp3)', default=settings.get('default_music_file'))
    parser.add_argument('-n', '--num-images', type=int, help='Number of images to be generated', default=settings.get('default_num_images', 5))
    parser.add_argument('-i', '--image-output-folder', type=str, help='Path for the folder where images will be saved', default=settings.get('default_image_output_folder', 'image_output'))
    parser.add_argument('-o', '--output-file', type=str, help='Path for the output video file', default=settings.get('default_output_file'))

    args = parser.parse_args()
    main(args)
