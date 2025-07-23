from django.shortcuts import render, get_object_or_404, redirect
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Q
from django.contrib.auth.decorators import login_required
from .models import College, Course, PlacementData, NIRFRanking
from .forms import CustomUserCreationForm

import requests
import json

# Gemini AI setup
GEMINI_API_KEY = "AIzaSyAgCMrGw7bkeM7l5D-_e5u8CYN8hO0bpFk"
GEMINI_API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"

# --- Pagination ---
COLLEGES_PER_PAGE = 10

# --- Views ---

def home(request):
    return render(request, 'colleges/home.html')

@login_required
def college_list(request):
    colleges_queryset = College.objects.all().order_by('official_name')

    search_query = request.GET.get('search_query')
    state_filter = request.GET.get('state')
    ownership_filter = request.GET.get('ownership_type')
    course_filter_code = request.GET.get('course')
    min_avg_package = request.GET.get('min_avg_package')

    if search_query:
        colleges_queryset = colleges_queryset.filter(
            Q(official_name__icontains=search_query) |
            Q(short_name__icontains=search_query) |
            Q(city__icontains=search_query) |
            Q(state__icontains=search_query)
        )
    if state_filter:
        colleges_queryset = colleges_queryset.filter(state=state_filter)
    if ownership_filter:
        colleges_queryset = colleges_queryset.filter(ownership_type=ownership_filter)
    if course_filter_code:
        colleges_queryset = colleges_queryset.filter(collegecourse__course__short_code=course_filter_code).distinct()
    if min_avg_package:
        try:
            min_avg_package = float(min_avg_package)
            colleges_queryset = colleges_queryset.filter(placement_data__average_package_lpa__gte=min_avg_package).distinct()
        except ValueError:
            pass

    colleges_queryset = colleges_queryset.prefetch_related(
        'nirf_rankings', 'placement_data', 'collegecourse_set__course'
    )

    paginator = Paginator(colleges_queryset, COLLEGES_PER_PAGE)
    page_number = request.GET.get('page')

    try:
        page_obj = paginator.page(page_number)
    except (EmptyPage, PageNotAnInteger):
        page_obj = paginator.page(1)

    for college in page_obj.object_list:
        college.nirf_rankings_sorted = sorted(college.nirf_rankings.all(), key=lambda x: x.year, reverse=True)
        college.latest_nirf = college.nirf_rankings_sorted[0] if college.nirf_rankings_sorted else None

        college.placement_data_sorted = sorted(college.placement_data.all(), key=lambda x: x.year, reverse=True)
        college.latest_placement = college.placement_data_sorted[0] if college.placement_data_sorted else None

    context = {
        'colleges': page_obj.object_list,
        'page_obj': page_obj,
        'states': College.objects.values_list('state', flat=True).distinct().order_by('state'),
        'courses': Course.objects.all().order_by('name'),
        'ownership_types': College.ownership_choices,
        'request': request
    }

    if request.headers.get('HX-Request'):
        return render(request, 'colleges/college_cards.html', context)
    return render(request, 'colleges/college_list.html', context)

@login_required
def college_detail(request, college_id):
    college = get_object_or_404(College, pk=college_id)
    college.nirf_rankings_sorted = sorted(college.nirf_rankings.all(), key=lambda x: x.year, reverse=True)
    college.placement_data_sorted = sorted(college.placement_data.all(), key=lambda x: x.year, reverse=True)

    return render(request, 'colleges/college_detail.html', {'college': college})

@login_required
def profile_view(request):
    return render(request, 'colleges/profile.html', {'user': request.user})

def about_view(request):
    return render(request, 'colleges/about.html')

@login_required
def ai_recommendation(request):
    """
    Handles AI recommendations using Gemini API.
    - On GET request, displays a form for user input (prompt.html).
    - On POST request, processes the prompt (factual vs. recommendation) and displays results (ai_recommendation_results.html).
    """
    if request.method == 'GET':
        # If it's a GET request, just display the form for the user to input their prompt.
        return render(request, 'colleges/prompt.html') # Corrected template path

    elif request.method == 'POST':
        recommended_colleges = []
        error_message = None
        user_prompt = request.POST.get('user_prompt', '').strip()
        direct_answer = None # Variable to store direct factual answers from Gemini

        if not user_prompt:
            error_message = "Please enter a prompt to get recommendations."
        else:
            intent_gemini_response_text = None # Initialize for error handling scope
            filter_gemini_response_text = None # Initialize for error handling scope
            try:
                # --- Step 1: Use Gemini to determine intent (factual vs. recommendation) ---
                intent_prompt = f"""
                Analyze the following user query and determine its intent.
                Query: "{user_prompt}"

                Is the user asking a direct factual question about a specific college or a specific data point (e.g., "What is the highest package of IIT Bombay?", "Tell me about NIT Trichy's NIRF rank in 2024?", "What is the address of IIT Delhi?")?
                Or is the user asking for college recommendations/filtering based on criteria (e.g., "Suggest top colleges in Delhi for CSE", "Find colleges with good placements in Maharashtra")?

                Return a JSON object with a single boolean key "is_factual_query".
                If it's a direct factual question, set "is_factual_query": true.
                If it's a recommendation/filtering request, set "is_factual_query": false.
                Example for factual: {{"is_factual_query": true}}
                Example for recommendation: {{"is_factual_query": false}}
                """

                print(f"DEBUG: User Prompt: '{user_prompt}'") # DEBUG PRINT
                print(f"DEBUG: Sending Intent Prompt to Gemini:\n{intent_prompt}") # DEBUG PRINT

                intent_payload = {
                    "contents": [{"role": "user", "parts": [{"text": intent_prompt}]}],
                    "generationConfig": {
                        "responseMimeType": "application/json",
                        "responseSchema": {
                            "type": "OBJECT",
                            "properties": {
                                "is_factual_query": {"type": "BOOLEAN"}
                            }
                        }
                    }
                }

                headers = {'Content-Type': 'application/json'}
                intent_response = requests.post(GEMINI_API_URL, headers=headers, data=json.dumps(intent_payload))
                intent_response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
                
                # Check if 'candidates' and its structure exist before accessing
                if intent_response.json().get('candidates') and intent_response.json()['candidates'][0].get('content') and intent_response.json()['candidates'][0]['content'].get('parts'):
                    intent_gemini_response_text = intent_response.json()['candidates'][0]['content']['parts'][0]['text']
                    parsed_intent = json.loads(intent_gemini_response_text)
                else:
                    raise ValueError("Gemini intent response is empty or malformed.")


                print(f"DEBUG: Gemini Intent Response (Raw Text): '{intent_gemini_response_text}'") # DEBUG PRINT
                print(f"DEBUG: Parsed Intent: {parsed_intent}") # DEBUG PRINT

                if parsed_intent.get('is_factual_query', False):
                    print("DEBUG: Intent detected as FACTUAL QUERY.") # DEBUG PRINT
                    # --- If it's a factual query, send the original prompt directly to Gemini for a natural language answer ---
                    factual_answer_prompt = f"""
                    Answer the following question concisely and directly. If you don't have the exact data for a specific year, provide the latest available or a general statement.
                    Question: "{user_prompt}"
                    """
                    print(f"DEBUG: Sending Factual Answer Prompt to Gemini:\n{factual_answer_prompt}") # DEBUG PRINT
                    factual_answer_payload = {
                        "contents": [{"role": "user", "parts": [{"text": factual_answer_prompt}]}]
                    }
                    factual_answer_response = requests.post(GEMINI_API_URL, headers=headers, data=json.dumps(factual_answer_payload))
                    factual_answer_response.raise_for_status() # Raise HTTPError
                    
                    if factual_answer_response.json().get('candidates') and factual_answer_response.json()['candidates'][0].get('content') and factual_answer_response.json()['candidates'][0]['content'].get('parts'):
                        direct_answer = factual_answer_response.json()['candidates'][0]['content']['parts'][0]['text']
                    else:
                        raise ValueError("Gemini factual answer response is empty or malformed.")
                    print(f"DEBUG: Gemini Direct Answer: '{direct_answer}'") # DEBUG PRINT

                else:
                    print("DEBUG: Intent detected as RECOMMENDATION/FILTERING QUERY.") # DEBUG PRINT
                    # --- If it's a recommendation/filtering query, proceed with local DB lookup (original logic) ---
                    filter_prompt_text = f"""
                    You are an expert college counselor. A user is looking for engineering college recommendations in India.
                    Their preferences are: "{user_prompt}"

                    Based on these preferences, identify the key criteria for filtering colleges.
                    Return the criteria as a JSON object with the following possible keys:
                    - "state": string (e.g., "Delhi", "Maharashtra")
                    - "ownership_type": string ("Government", "Private", "Deemed", "Government-Aided")
                    - "course_short_code": string (e.g., "CSE", "MECH", "ECE", "CIVIL") - use short codes if a specific branch is mentioned.
                    - "min_nirf_rank": integer (e.g., 50 for "under 50 rank", 100 for "top 100")
                    - "max_nirf_rank": integer (e.g., 10 for "top 10")
                    - "min_avg_package_lpa": float (e.g., 8.0 for "good placements around 8 LPA")
                    - "city": string (e.g., "Mumbai", "Bengaluru")

                    If a criterion is not mentioned or cannot be clearly inferred, omit that key from the JSON.
                    Ensure the JSON is perfectly valid and contains only the keys mentioned above.
                    Example output for recommendation:
                    {{
                        "state": "Maharashtra",
                        "ownership_type": "Private",
                        "course_short_code": "CSE",
                        "min_avg_package_lpa": 10.0
                    }}
                    """
                    print(f"DEBUG: Sending Filter Prompt to Gemini:\n{filter_prompt_text}") # DEBUG PRINT

                    filter_payload = {
                        "contents": [{"role": "user", "parts": [{"text": filter_prompt_text}]}],
                        "generationConfig": {
                            "responseMimeType": "application/json",
                            "responseSchema": {
                                "type": "OBJECT",
                                "properties": {
                                    "state": {"type": "STRING"},
                                    "ownership_type": {"type": "STRING"},
                                    "course_short_code": {"type": "STRING"},
                                    "min_nirf_rank": {"type": "INTEGER"},
                                    "max_nirf_rank": {"type": "INTEGER"},
                                    "min_avg_package_lpa": {"type": "NUMBER"},
                                    "city": {"type": "STRING"}
                                }
                            }
                        }
                    }

                    filter_response = requests.post(GEMINI_API_URL, headers=headers, data=json.dumps(filter_payload))
                    filter_response.raise_for_status() # Ensure HTTP errors are caught
                    
                    if filter_response.json().get('candidates') and filter_response.json()['candidates'][0].get('content') and filter_response.json()['candidates'][0]['content'].get('parts'):
                        filter_gemini_response_text = filter_response.json()['candidates'][0]['content']['parts'][0]['text']
                        parsed_criteria = json.loads(filter_gemini_response_text)
                    else:
                        raise ValueError("Gemini filter response is empty or malformed.")

                    print(f"DEBUG: Gemini Filter Response (Raw Text): '{filter_gemini_response_text}'") # DEBUG PRINT
                    print(f"DEBUG: Parsed Filter Criteria: {parsed_criteria}") # DEBUG PRINT

                    query_set = College.objects.all()

                    # --- IMPORTANT: Standardize ownership_type values before filtering ---
                    # Ensure the ownership_map accounts for both "Government" and "GOVT"
                    ownership_map = {
                        'government': 'Government', # This is the full label in the model's choices
                        'govt': 'Government',
                        'private': 'Private',
                        'deemed': 'Deemed University/Deemed to be University',
                        'government-aided': 'Government-Aided',
                        # Add other mappings if Gemini might return variations
                    }
                    
                    if 'state' in parsed_criteria:
                        query_set = query_set.filter(state__iexact=parsed_criteria['state'])
                        print(f"DEBUG: Filtered by state: {parsed_criteria['state']}") # DEBUG PRINT
                    if 'city' in parsed_criteria:
                        query_set = query_set.filter(city__iexact=parsed_criteria['city'])
                        print(f"DEBUG: Filtered by city: {parsed_criteria['city']}") # DEBUG PRINT
                    if 'ownership_type' in parsed_criteria:
                        # Convert parsed ownership_type to the exact value used in College.ownership_choices
                        # Use .get() with a default of None to prevent KeyError if type not found
                        model_ownership_value = ownership_map.get(parsed_criteria['ownership_type'].lower()) 
                        if model_ownership_value:
                            query_set = query_set.filter(ownership_type=model_ownership_value)
                            print(f"DEBUG: Filtered by ownership: {model_ownership_value} (Parsed: {parsed_criteria['ownership_type']})")
                        else:
                            print(f"DEBUG: Warning: Unknown ownership_type parsed: {parsed_criteria['ownership_type']}")
                            pass # Do not filter by ownership if unknown
                            
                    if 'course_short_code' in parsed_criteria:
                        query_set = query_set.filter(
                            collegecourse__course__short_code__iexact=parsed_criteria['course_short_code']
                        ).distinct()
                        print(f"DEBUG: Filtered by course: {parsed_criteria['course_short_code']}") # DEBUG PRINT
                    if 'min_nirf_rank' in parsed_criteria:
                        query_set = query_set.filter(
                            nirf_rankings__engineering_rank__lte=parsed_criteria['min_nirf_rank']
                        ).distinct()
                        print(f"DEBUG: Filtered by min NIRF rank: {parsed_criteria['min_nirf_rank']}") # DEBUG PRINT
                    if 'max_nirf_rank' in parsed_criteria:
                        query_set = query_set.filter(
                            nirf_rankings__engineering_rank__gte=parsed_criteria['max_nirf_rank']
                        ).distinct()
                        print(f"DEBUG: Filtered by max NIRF rank: {parsed_criteria['max_nirf_rank']}") # DEBUG PRINT
                    if 'min_avg_package_lpa' in parsed_criteria:
                        query_set = query_set.filter(
                            placement_data__average_package_lpa__gte=parsed_criteria['min_avg_package_lpa']
                        ).distinct()
                        print(f"DEBUG: Filtered by min avg package: {parsed_criteria['min_avg_package_lpa']}") # DEBUG PRINT

                    recommended_colleges = query_set.order_by('official_name').prefetch_related(
                        'nirf_rankings',
                        'placement_data',
                        'collegecourse_set__course'
                    )
                    print(f"DEBUG: Number of colleges found after DB query: {recommended_colleges.count()}") # DEBUG PRINT

                    for college in recommended_colleges:
                        college.nirf_rankings_sorted = sorted(
                            list(college.nirf_rankings.all()),
                            key=lambda x: x.year,
                            reverse=True
                        )
                        college.latest_nirf = college.nirf_rankings_sorted[0] if college.nirf_rankings_sorted else None

                        college.placement_data_sorted = sorted(
                            list(college.placement_data.all()),
                            key=lambda x: x.year,
                            reverse=True
                        )
                        college.latest_placement = college.placement_data_sorted[0] if college.placement_data_sorted else None

            except requests.exceptions.RequestException as e:
                error_message = f"Error connecting to Gemini API: {e}. Please check your API key and internet connection."
                print(f"ERROR: Gemini API Request Error: {e}") # DEBUG PRINT
            except json.JSONDecodeError as e:
                error_message = f"Error parsing Gemini's response. It might not be valid JSON: {e}. Raw response: {intent_gemini_response_text if 'intent_gemini_response_text' in locals() else filter_gemini_response_text if 'filter_gemini_response_text' in locals() else 'N/A'}"
                print(f"ERROR: Gemini JSON Decode Error: {e}. Raw response: {intent_gemini_response_text if 'intent_gemini_response_text' in locals() else filter_gemini_response_text if 'filter_gemini_response_text' in locals() else 'N/A'}") # DEBUG PRINT
            except KeyError as e:
                error_message = f"Unexpected response structure from Gemini API: Missing key {e}. Raw response: {intent_response.json() if 'intent_response' in locals() else filter_response.json() if 'filter_response' in locals() else 'N/A'}"
                print(f"ERROR: Gemini Response Structure Error: {e}. Raw response: {intent_response.json() if 'intent_response' in locals() else filter_response.json() if 'filter_response' in locals() else 'N/A'}") # DEBUG PRINT
            except Exception as e:
                error_message = f"An unexpected error occurred: {e}"
                print(f"ERROR: General AI Recommendation Error: {e}") # DEBUG PRINT

        context = {
            'recommended_colleges': recommended_colleges,
            'error_message': error_message,
            'user_prompt': user_prompt,
            'direct_answer': direct_answer
        }
        return render(request, 'colleges/ai_recommendation_results.html', context) # Corrected template path


def register(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('login')
    else:
        form = CustomUserCreationForm()
        
    return render(request, 'registration/register.html', {'form': form})