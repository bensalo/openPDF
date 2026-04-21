from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.http import FileResponse, Http404, JsonResponse
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.contrib import messages
from prod import pdftemplate, CVprod
from .models import Generation, Template, Field, Dataset
import cv2
import uuid, os, io, json, requests, time

APPDATA_PATH = 'media/'
AVAILABLE_FONTS = ['Helvetica', 'Courier']
FIELD_TYPES = ['text', 'textarea', 'checkbox']

def index(request):
    """
    project root view
    - list templates
    """
    context = {}

    context["templates"] = Template.objects.all()
    context["datasets"] = Dataset.objects.all()
    return render(request, "index.html", context)

def create_template(request):
    """
    create new template
    - form
    """
    context = {}

    context["AVAILABLE_FONTS"] = AVAILABLE_FONTS

    if request.POST:

        form_dict = request.POST.dict()
        
        template_id = str(uuid.uuid4())

        form_dict["temp_id"] = template_id
        
        source_file = request.FILES['source_file']
        source_file_path = default_storage.save(f'source_files/{template_id}_{source_file.name}', ContentFile(source_file.read()))
        
        form_dict["source_template"] = {
            "index": form_dict.get("template_source_index"),
            "pages": form_dict.get("template_source_pages"),
            "file_path": f'{template_id}_{source_file.name}'
        }

        # TODO only one attachments gets attached - everything else is skipped
    
        attachment_index = []
        attachments = []

        for key, value in request.POST.items():
            if key.startswith('attachment_name'):
                key_index = key.split('_')[2]
                attachment_index.append(key_index)

        print(request.FILES)

        for key in attachment_index:

            attachment_file = request.FILES[f'attachment_file_{key}']
            attachment_file_path = default_storage.save(f'attachments/{template_id}_{attachment_file.name}', ContentFile(attachment_file.read()))
            
            attachments.append({
                'name': form_dict.get(f'attachment_name_{key}'),
                'index': form_dict.get(f'attachment_index_{key}'),
                'pages': form_dict.get(f'attachment_pages_{key}'),
                'file_path': f'{template_id}_{attachment_file.name}'
            })            

        form_dict["source_attachments"] = attachments

        pdftemplate.Pdf_template(form_dict=form_dict)

        return redirect(f'/{template_id}/')

    return render(request, "create_template.html", context)

def generate_template(request):
    """
    predict pdf, generate template
    - form
    """
    context = {}

    if request.POST:
        form_dict = request.POST.dict()
        
        # Get detection method and LLM settings
        detection_method = request.POST.get('detection_method', 'traditional')
        use_llm = (detection_method == 'llm')
        llm_provider = request.POST.get('llm_provider', 'gemini') if use_llm else None
        
        template_id = str(uuid.uuid4())
        form_dict["temp_id"] = template_id
        form_dict["field_detection_method"] = detection_method
        
        source_file = request.FILES['source_file']
        source_file_path = default_storage.save(f'source_files/{template_id}_{source_file.name}', ContentFile(source_file.read()))
        
        try:
            # Try with selected method - now returns llm_details
            prediction, pdf_image, prediction_image, llm_details = CVprod.process_to_template(
                default_storage.path(source_file_path),
                use_llm=use_llm,
                llm_provider=llm_provider
            )
            
            # Store LLM details if available
            if llm_details:
                form_dict["llm_details"] = llm_details
            
            # Check if prediction is None or empty (LLM failed)
            if prediction is None or len(prediction) == 0:
                raise Exception("No fields detected")
             
        except Exception as e:
            # If LLM failed, try fallback to traditional
            if use_llm:
                try:
                    # Retry with traditional method
                    prediction, pdf_image, prediction_image, fallback_details = CVprod.process_to_template(
                        default_storage.path(source_file_path),
                        use_llm=False
                    )
                    
                    # Mark as fallback in details
                    if llm_details:  # Use original llm_details if available
                        llm_details["results"]["fallback_used"] = True
                        form_dict["llm_details"] = llm_details
                    
                    form_dict["field_detection_method"] = "traditional"  # Update to reflect actual method used
                    
                    if prediction is None or len(prediction) == 0:
                        return render(request, "generate_template.html", context)
                        
                    
                except Exception as fallback_error:
                    return render(request, "generate_template.html", context)
            else:
                # Traditional method failed (no fallback)
                return render(request, "generate_template.html", context)
        
        # Save images (this happens for whichever method succeeded)
        pdf_image.save(f'media/source_files/{template_id}_label.jpg', 'JPEG')
        cv2.imwrite(f'media/source_files/{template_id}_prediction.jpg', prediction_image)
        
        form_dict["fields"] = prediction
        
        form_dict["source_template"] = {
            "index": form_dict.get("template_source_index", 1),
            "pages": form_dict.get("template_source_pages", 1),
            "file_path": f'{template_id}_{source_file.name}',
            "label_path": f'{template_id}_label.jpg',
            "prediction_path": f'{template_id}_prediction.jpg'
        }

        # Handle attachments
        attachment_index = []
        attachments = []

        for key, value in request.POST.items():
            if key.startswith('attachment_name'):
                key_index = key.split('_')[2]
                attachment_index.append(key_index)

        for key in attachment_index:
            if f'attachment_file_{key}' in request.FILES:
                attachment_file = request.FILES[f'attachment_file_{key}']
                attachment_file_path = default_storage.save(
                    f'attachments/{template_id}_{attachment_file.name}', 
                    ContentFile(attachment_file.read())
                )
                
                attachments.append({
                    'name': form_dict.get(f'attachment_name_{key}'),
                    'index': form_dict.get(f'attachment_index_{key}'),
                    'pages': form_dict.get(f'attachment_pages_{key}'),
                    'file_path': f'{template_id}_{attachment_file.name}'
                })

        form_dict["source_attachments"] = attachments

        # Create the PDF template
        pdftemplate.Pdf_template(form_dict=form_dict)
        
        return redirect('/')

    return render(request, "generate_template.html", context)

def check_llm_status(request):
    """Simple LLM status check with test request"""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'POST only'})
    
    try:
        data = json.loads(request.body)
        provider = data.get('provider')
        
        from dotenv import load_dotenv
        load_dotenv('prod/.env')
        
        # Prepare test prompt
        test_prompt = "Are you there? Reply with: Yes, I am working."
        
        if provider == 'gemini':
            api_key = os.getenv('GEMINI_API_KEY')
            if not api_key:
                return JsonResponse({'status': 'error', 'message': 'No API key'})
            
            response = requests.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{os.getenv('GEMINI_MODEL', 'gemini-2.5-flash')}:generateContent?key={api_key}",
                json={'contents': [{'parts': [{'text': test_prompt}]}]},
                timeout=5
            )
            
        elif provider == 'openai':
            api_key = os.getenv('OPENAI_API_KEY')
            if not api_key:
                return JsonResponse({'status': 'error', 'message': 'No API key'})
            
            response = requests.post(
                'https://api.openai.com/v1/chat/completions',
                headers={'Authorization': f'Bearer {api_key}'},
                json={
                    'model': os.getenv('OPENAI_MODEL', 'gpt-4'),
                    'messages': [{'role': 'user', 'content': test_prompt}],
                    'max_tokens': 20
                },
                timeout=5
            )
            
        elif provider == 'ollama':
            response = requests.post(
                f"{os.getenv('OLLAMA_HOST', 'http://localhost:11434')}/api/generate",
                json={'model': os.getenv('OLLAMA_MODEL', 'llama2'), 'prompt': test_prompt, 'stream': False},
                timeout=5
            )
        else:
            return JsonResponse({'status': 'error', 'message': 'Unknown provider'})
        
        # Return status code and response
        if response.status_code == 200:
            return JsonResponse({
                'status': 'ok',
                'message': f'✅ Status {response.status_code}: Working',
                'response': response.json()
            })
        else:
            return JsonResponse({
                'status': 'error',
                'message': f'❌ Status {response.status_code}',
                'response': response.text[:200]  # First 200 chars of error
            })
            
    except requests.Timeout:
        return JsonResponse({'status': 'error', 'message': '⏱️ Timeout'})
    except requests.ConnectionError:
        return JsonResponse({'status': 'error', 'message': '🔌 Connection failed'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': f'❌ {str(e)[:50]}'})

def template_detail(request, temp_id):
    """
    detail template view
    """
    context = {}
        
    template_object = pdftemplate.Pdf_template(temp_id=temp_id)

    context["template"] = template_object.get_template()
    context["fields"] = template_object.get_fields()

    return render(request, "template_detail.html", context)

def file_response(request, file_path, file_type):
    if file_type not in ['source_files', 'attachments']:
        raise Http404("Invalid file type")

    full_path = f"{file_type}/{file_path}"
    
    if default_storage.exists(full_path):
        file = default_storage.open(full_path, 'rb')
        return FileResponse(file)
    else:
        raise Http404("File not found")

def template_edit(request, temp_id):
    """
    edit template
    """
    context = {}

    context["AVAILABLE_FONTS"] = AVAILABLE_FONTS
    context["FIELD_TYPES"] = FIELD_TYPES

    template_object = pdftemplate.Pdf_template(temp_id=temp_id)
    
    if request.method == 'POST':
        template_object.update_template(request.POST.dict(), request.FILES)

    context["template"] = template_object.get_template()
    context["fields"] = template_object.get_fields()

    return render(request, "template_edit.html", context)


def template_new_pdf(request, temp_id, gen_id=None):
    """
    New PDF from template with optional preload from a specific generation.
    """
    context = {}

    # Load the template object
    template_object = pdftemplate.Pdf_template(temp_id=temp_id)
    context["template"] = template_object.get_template()
    context["fields"] = template_object.get_fields()
    context["datasets"] = Dataset.objects.all()

    # Preload data from the given generation or the latest one
    if gen_id:
        generation = get_object_or_404(Generation, id=gen_id)
        context["preload_data"] = generation.field_values
    else:
        #try:
        #    latest_generation = Generation.objects.filter(template_id=temp_id).latest('created_at')
        #    context["preload_data"] = latest_generation.field_values
        #except Generation.DoesNotExist:
        #    context["preload_data"] = {}

        context["preload_data"] = {}

    if request.method == 'POST':
        form_dict = request.POST.dict()
        output_file = template_object.gen_pdf(form_dict)

        base_filename = f'{form_dict.get("output_filename", "openPDF_output")}.pdf'

        storage_path = f'generated/{uuid.uuid4()}_{base_filename}'

        file_path = default_storage.save(storage_path, output_file)

        form_dict.pop("csrfmiddlewaretoken", None)
        form_dict.pop("output_filename", None)

        generation = Generation(name=base_filename, field_values=form_dict, template=template_object.get_template())
        generation.file_path = file_path
        generation.save()

        return FileResponse(
            default_storage.open(file_path), 
            as_attachment=True, 
            filename=base_filename
        )

    return render(request, "new.html", context)


def new_dataset(request, gen_id):
    # Fetch the generation object based on the given ID
    generation = get_object_or_404(Generation, id=gen_id)

    if request.method == 'POST':
        # Get the dataset name from the form
        dataset_name = request.POST.get('dataset_name', '').strip()
        
        # Preselect fields and aliases from the form data
        selected_fields = {}
        field_aliases = {}
        for field_name in generation.field_values:
            # Check if the checkbox for this field is selected
            if f'active_{field_name}' in request.POST:
                # Get the field value and alias from the form
                field_value = request.POST.get(f'value_{field_name}', '').strip()
                alias = request.POST.get(f'alias_{field_name}', '').strip()
                selected_fields[field_name] = {
                    'value': field_value,
                    'alias': alias
                }

        # Create and save the new dataset
        dataset = Dataset(
            name=dataset_name,
            generation=generation,
            fields = selected_fields
        )
        dataset.save()

        # Redirect to a success page or another relevant view
        return redirect('datasets')

    # If GET request, prepare context for rendering the form
    context = {
        "fields": generation.field_values
    }
    return render(request, "new_dataset.html", context)

def datasets(request):
    context = {}
    context["datasets"] = Dataset.objects.all()    
    context["templates"] = Template.objects.all()
    return render(request, "datasets.html", context)

def dataset_detail(request, dataset_id):
    context = {}
    dataset = get_object_or_404(Dataset, id=dataset_id)
    if request.method == 'POST':
        dataset_name = request.POST.get('dataset_name', '').strip()

        dataset.name = dataset_name

        # Update fields and aliases
        updated_fields = {}
        for field_name, field_data in dataset.fields.items():
            field_value = request.POST.get(f'value_{field_name}', '').strip()
            alias = request.POST.get(f'alias_{field_name}', '').strip()
            updated_fields[field_name] = {
                'value': field_value,
                'alias': alias,
            }

        dataset.fields = updated_fields
        dataset.save()

        # Redirect to the same detail view with a success message
        return redirect('dataset_detail', dataset_id=dataset.id)
    context["dataset"]  = dataset
    return render(request, "dataset_detail.html", context)

def dataset_use(request, dataset_id, temp_id):
    context = {}

    # Load the template object
    template_object = pdftemplate.Pdf_template(temp_id=temp_id)
    context["template"] = template_object.get_template()
    context["fields"] = template_object.get_fields()
    context["datasets"] = Dataset.objects.all()


    # Preload data from the given generation or the latest one
    if dataset_id:
        dataset = get_object_or_404(Dataset, id=dataset_id)

        fields = dataset.fields
        # Add preloaded data for each field (using aliases or keys)
        preload_data = {}
        for field_name, field_data in fields.items():
            preload_data[field_name] = field_data.get('value', '')
            alias = field_data.get('alias')
            if alias and alias not in preload_data:
                preload_data[alias] = field_data.get('value', '')
        context["preload_data"] = preload_data

    else:
        context["preload_data"] = {}

    if request.method == 'POST':
        form_dict = request.POST.dict()
        output_file = template_object.gen_pdf(form_dict)

        base_filename = f'{form_dict.get("output_filename", "openPDF_output")}.pdf'

        unique_id = uuid.uuid4()
        storage_path = f'generated/{unique_id}_{base_filename}'
        
        file_path = default_storage.save(storage_path, output_file)

        if hasattr(output_file, 'seek'):
            output_file.seek(0)

        form_dict.pop("csrfmiddlewaretoken", None)
        form_dict.pop("output_filename", None)

        generation = Generation(name=base_filename, field_values=form_dict, template=template_object.get_template())
        generation.file_path = file_path # Hier liegt jetzt der Pfad MIT der UUID
        generation.save()

        return FileResponse(output_file, as_attachment=True, filename=base_filename)

    return render(request, "new.html", context)

def settings_view(request):
    if request.method == 'POST':
        # Handle file upload
        if 'font_file' in request.FILES:
            font_file = request.FILES['font_file']
            font_file_path = os.path.join('fonts', font_file.name)
            default_storage.save(font_file_path, font_file)
        
        # Handle other settings here
        # Example: saving settings to a database or a file
        
        return redirect('settings_view')

    # Display current settings
    context = {
        # Load current settings here
    }
    return render(request, 'settings.html', context)


def history_view(request):

    # load all generations from model
    generations = Generation.objects.order_by("created_at")
    # actions -> Pre-Load Form with data  


    context = {}
    context["generations"] = generations
    return render(request, 'history.html', context)

def history_detail_view(request, gen_id):
    """
    Displays detailed information about a specific generation.
    """
    generation = get_object_or_404(Generation, id=gen_id)
    context = {
        'generation': generation,
        'field_values': generation.field_values
    }
    return render(request, 'history_detail.html', context)