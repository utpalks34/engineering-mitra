# C:\Users\utpal\Desktop\Techsetu\colleges\admin.py
from django.contrib import admin
from .models import College, Course, CollegeCourse, NIRFRanking, PlacementData, JEECutoff

# Admin for Course model (remains separate as it's not an inline of College)
@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ('name', 'short_code')
    search_fields = ('name', 'short_code')

# Inline models for College
class CollegeCourseInline(admin.TabularInline):
    model = CollegeCourse
    extra = 1 # Number of empty forms to display
    fields = ('course', 'intake_capacity', 'fees_per_year')

class NIRFRankingInline(admin.TabularInline):
    model = NIRFRanking
    extra = 1
    fields = ('year', 'overall_rank', 'overall_score', 'engineering_rank', 'engineering_score')

class PlacementDataInline(admin.TabularInline):
    model = PlacementData
    extra = 1
    fields = ('year', 'highest_package_lpa', 'average_package_lpa', 'median_package_lpa', 'placement_percentage', 'students_placed', 'total_students')

class JEECutoffInline(admin.TabularInline):
    model = JEECutoff
    extra = 1
    fields = ('course', 'year', 'category', 'gender', 'opening_rank', 'closing_rank')


# Register CollegeAdmin with all its configurations in one place
@admin.register(College)
class CollegeAdmin(admin.ModelAdmin):
    list_display = ('official_name', 'city', 'state', 'ownership_type', 'established_year')
    search_fields = ('official_name', 'short_name', 'city', 'state')
    list_filter = ('ownership_type', 'state', 'established_year')
    
    # All inlines are listed here
    inlines = [NIRFRankingInline, PlacementDataInline, CollegeCourseInline, JEECutoffInline] 
    
    # Fieldsets organize the main College model fields
    fieldsets = (
        (None, {
            'fields': ('official_name', 'short_name', 'description', 'official_website', 'email', 'phone_number')
        }),
        ('Location & Establishment', {
            'fields': ('city', 'state', 'address', 'pincode', 'established_year', 'campus_area_acres')
        }),
        ('Institutional Details', {
            'fields': ('ownership_type',)
        }),
    )