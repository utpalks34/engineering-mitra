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
    if request.method == 'GET':
        return render(request, 'colleges/prompt.html')

    elif request.method == 'POST':
        recommended_colleges = []
        error_message = None
        user_prompt = request.POST.get('user_prompt', '').strip()
        direct_answer = None

        if not user_prompt:
            error_message = "Please enter a prompt to get recommendations."
        else:
            try:
                intent_payload = {
                    "contents": [{"role": "user", "parts": [{"text": f"""
                    Analyze the following user query and determine its intent:
                    "{user_prompt}"
                    Return a JSON like: {{"is_factual_query": true}} or false.
                    """}]}],
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
                intent_response.raise_for_status()
                parsed_intent = json.loads(intent_response.json()['candidates'][0]['content']['parts'][0]['text'])

                if parsed_intent.get('is_factual_query', False):
                    factual_answer_payload = {
                        "contents": [{"role": "user", "parts": [{"text": f"""
                        Answer this factually and concisely:
                        "{user_prompt}"
                        """}]}]
                    }
                    factual_answer_response = requests.post(GEMINI_API_URL, headers=headers, data=json.dumps(factual_answer_payload))
                    factual_answer_response.raise_for_status()
                    direct_answer = factual_answer_response.json()['candidates'][0]['content']['parts'][0]['text']
                else:
                    filter_payload = {
                        "contents": [{"role": "user", "parts": [{"text": f"""
                        Based on this college query: "{user_prompt}"
                        Return filtering JSON like:
                        {{
                            "state": "Maharashtra",
                            "ownership_type": "Private",
                            "course_short_code": "CSE",
                            "min_avg_package_lpa": 10.0
                        }}
                        Only include fields you can clearly infer.
                        """}]}],
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
                    parsed_criteria = json.loads(filter_response.json()['candidates'][0]['content']['parts'][0]['text'])

                    query_set = College.objects.all()
                    if 'state' in parsed_criteria:
                        query_set = query_set.filter(state__iexact=parsed_criteria['state'])
                    if 'city' in parsed_criteria:
                        query_set = query_set.filter(city__iexact=parsed_criteria['city'])
                    if 'ownership_type' in parsed_criteria:
                        ownership_map = {label.lower(): value for value, label in College.ownership_choices}
                        model_ownership = ownership_map.get(parsed_criteria['ownership_type'].lower())
                        if model_ownership:
                            query_set = query_set.filter(ownership_type=model_ownership)
                    if 'course_short_code' in parsed_criteria:
                        query_set = query_set.filter(collegecourse__course__short_code__iexact=parsed_criteria['course_short_code']).distinct()
                    if 'min_nirf_rank' in parsed_criteria:
                        query_set = query_set.filter(nirf_rankings__engineering_rank__lte=parsed_criteria['min_nirf_rank']).distinct()
                    if 'max_nirf_rank' in parsed_criteria:
                        query_set = query_set.filter(nirf_rankings__engineering_rank__gte=parsed_criteria['max_nirf_rank']).distinct()
                    if 'min_avg_package_lpa' in parsed_criteria:
                        query_set = query_set.filter(placement_data__average_package_lpa__gte=parsed_criteria['min_avg_package_lpa']).distinct()

                    recommended_colleges = query_set.order_by('official_name').prefetch_related(
                        'nirf_rankings', 'placement_data', 'collegecourse_set__course'
                    )

                    for college in recommended_colleges:
                        college.nirf_rankings_sorted = sorted(college.nirf_rankings.all(), key=lambda x: x.year, reverse=True)
                        college.latest_nirf = college.nirf_rankings_sorted[0] if college.nirf_rankings_sorted else None
                        college.placement_data_sorted = sorted(college.placement_data.all(), key=lambda x: x.year, reverse=True)
                        college.latest_placement = college.placement_data_sorted[0] if college.placement_data_sorted else None

            except Exception as e:
                error_message = f"Something went wrong with AI processing: {str(e)}"

        return render(request, 'colleges/ai_recommendation_results.html', {
            'recommended_colleges': recommended_colleges,
            'error_message': error_message,
            'user_prompt': user_prompt,
            'direct_answer': direct_answer
        })

# --- User Registration View ---
def register(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('login')  # redirect to named URL pattern for login
    else:
        form = CustomUserCreationForm()
        
    return render(request, 'registration/register.html', {'form': form})
