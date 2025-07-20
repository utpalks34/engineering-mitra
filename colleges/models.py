# C:\Users\utpal\Desktop\Techsetu\colleges\models.py

from django.db import models

class College(models.Model):
    """
    Represents a college with its basic information.
    """
    ownership_choices = [
        ('Government', 'Government'),
        ('Private', 'Private'),
        ('Deemed', 'Deemed University/Deemed to be University'),
        ('Government-Aided', 'Government-Aided'),
    ]

    official_name = models.CharField(max_length=255, unique=True)
    short_name = models.CharField(max_length=100, blank=True, null=True) # e.g., IIT Bombay, NIT Trichy
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    ownership_type = models.CharField(max_length=50, choices=ownership_choices, default='Government')
    official_website = models.URLField(max_length=200, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    pincode = models.CharField(max_length=10, blank=True, null=True)
    email = models.EmailField(max_length=254, blank=True, null=True)
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    established_year = models.IntegerField(blank=True, null=True)
    campus_area_acres = models.FloatField(blank=True, null=True)
    description = models.TextField(blank=True, null=True)


    def __str__(self):
        return self.official_name

class NIRFRanking(models.Model):
    """
    Stores NIRF ranking data for a college for a specific year.
    """
    college = models.ForeignKey(College, on_delete=models.CASCADE, related_name='nirf_rankings')
    year = models.IntegerField()
    overall_rank = models.IntegerField(blank=True, null=True)
    overall_score = models.FloatField(blank=True, null=True)
    engineering_rank = models.IntegerField(blank=True, null=True)
    engineering_score = models.FloatField(blank=True, null=True)
    # Add other categories if needed, e.g., 'management_rank', 'medical_rank' etc.

    class Meta:
        unique_together = ('college', 'year') # A college can only have one NIRF ranking per year
        ordering = ['-year'] # Order by year descending by default

    def __str__(self):
        return f"{self.college.short_name or self.college.official_name} - NIRF {self.year}"

class Course(models.Model):
    """
    Represents an engineering course (e.g., Computer Science and Engineering).
    """
    name = models.CharField(max_length=200, unique=True)
    short_code = models.CharField(max_length=20, unique=True) # e.g., CSE, MECH, ECE

    def __str__(self):
        return self.short_code

class CollegeCourse(models.Model):
    """
    Intermediate model to represent which courses a college offers,
    along with specific details like fees and intake capacity.
    """
    college = models.ForeignKey(College, on_delete=models.CASCADE)
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    intake_capacity = models.IntegerField(blank=True, null=True)
    fees_per_year = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True,
                                        help_text="Fees per year in Lakhs (e.g., 1.5 for 1.5 Lakhs)")

    class Meta:
        unique_together = ('college', 'course') # A college offers a course only once

    def __str__(self):
        return f"{self.college.short_name or self.college.official_name} - {self.course.short_code}"

class PlacementData(models.Model):
    """
    Stores placement statistics for a college for a specific year.
    """
    college = models.ForeignKey(College, on_delete=models.CASCADE, related_name='placement_data')
    year = models.IntegerField()
    highest_package_lpa = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True,
                                                help_text="Highest package in Lakhs per annum")
    average_package_lpa = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True,
                                                help_text="Average package in Lakhs per annum")
    median_package_lpa = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True,
                                                help_text="Median package in Lakhs per annum")
    placement_percentage = models.FloatField(blank=True, null=True,
                                             help_text="Percentage of students placed (e.g., 90.5 for 90.5%)")
    students_placed = models.IntegerField(blank=True, null=True)
    total_students = models.IntegerField(blank=True, null=True)

    class Meta:
        unique_together = ('college', 'year') # A college can only have one placement record per year
        ordering = ['-year'] # Order by year descending by default

    def __str__(self):
        return f"{self.college.short_name or self.college.official_name} - Placements {self.year}"

class JEECutoff(models.Model):
    """
    Stores JEE Main/Advanced cutoff data for specific colleges and courses.
    You might need to refine this based on actual cutoff data structure (e.g., Round, Category).
    """
    college = models.ForeignKey(College, on_delete=models.CASCADE, related_name='jee_cutoffs')
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    year = models.IntegerField()
    # Assuming "Opening Rank" and "Closing Rank" for simplicity. Add more fields if needed (e.g., round, category, type)
    opening_rank = models.IntegerField(blank=True, null=True)
    closing_rank = models.IntegerField(blank=True, null=True)
    category = models.CharField(max_length=50, blank=True, null=True, help_text="e.g., OPEN, OBC-NCL, SC, ST, EWS")
    gender = models.CharField(max_length=10, blank=True, null=True, help_text="e.g., Gender-Neutral, Female-only")

    class Meta:
        # Example unique constraint, might need adjustment based on real data complexity
        unique_together = ('college', 'course', 'year', 'category', 'gender')
        ordering = ['-year', 'course__name', 'closing_rank']

    def __str__(self):
        return f"{self.college.short_name or self.college.official_name} - {self.course.short_code} {self.year} Cutoff ({self.category})"