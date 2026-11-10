import random
from django.core.management.base import BaseCommand
from django.db import transaction
from apps.schools.models import School
from apps.students.models import Student
from apps.academics.models import ClassLevel, Subject
from apps.teachers.models import Teacher
from apps.accounts.models import User
from kenyan_counties.models import County, Constituency, Ward

class Command(BaseCommand):
    help = 'Seeds 9 classes, 250 students, and CBC subjects for NAIROBI SCHOOL'

    def handle(self, *args, **kwargs):
        # 1. Target the specific school
        school = School.objects.filter(name__icontains='NAIROBI').first()
        if not school:
            self.stdout.write(self.style.ERROR("NAIROBI SCHOOL not found!"))
            return

        self.stdout.write(f"Targeting school: {school.name}")

        # 2. Create 9 Classes & Teachers
        class_names = [
            "Grade 1", "Grade 2", "Grade 3", 
            "Grade 4", "Grade 5", "Grade 6", 
            "Grade 7", "Grade 8", "Grade 9"
        ]
        
        created_classes = []
        created_teachers = []

        for i, name in enumerate(class_names):
            teacher_email = f"teacher{i+1}.nai@test.com"
            teacher_user, _ = User.objects.get_or_create(
                email=teacher_email,
                defaults={'username': teacher_email, 'first_name': 'Teacher', 'last_name': name, 'role': 'teacher', 'school': school}
            )
            
            teacher, created = Teacher.objects.get_or_create(
                user=teacher_user, 
                defaults={'school': school, 'employee_number': f"TCH-{i+1:03d}"}
            )
            created_teachers.append(teacher)

            cls, created = ClassLevel.objects.get_or_create(
                school=school, 
                name=name,
                defaults={'order': i+1}
            )
            created_classes.append(cls)

        self.stdout.write(self.style.SUCCESS(f"Verified/Created 9 classes and teachers."))

        # 3. Create CBC Subjects (Skipping the broken 'grade' link)
        subject_names = [
            "Mathematics", "English", "Kiswahili", 
            "Environmental Activities", "Science & Technology", 
            "Social Studies", "Religious Education", 
            "Creative Arts", "Agriculture"
        ]

        subjects_created = 0
        for sub_name in subject_names:
            Subject.objects.get_or_create(
                school=school,
                name=sub_name,
                # We skip 'grade' and 'teacher' because they are causing the DB conflict
            )
            subjects_created += 1
        
        self.stdout.write(self.style.SUCCESS(f"Created {subjects_created} Global CBC Subjects."))

        # 4. Generate 250 Kenyan Students (Only if we don't already have them)
        if Student.objects.filter(school=school).count() > 50:
            self.stdout.write(self.style.SUCCESS("Students already seeded. Skipping student creation to avoid duplicates."))
            return

        first_names_m = ["Brian", "Kevin", "Dennis", "Samuel", "John", "Peter", "Collins", "Victor", "Emmanuel", "Felix", "Kelvin", "Elijah", "Mark", "Daniel", "Alex"]
        first_names_f = ["Faith", "Mercy", "Joy", "Grace", "Sharon", "Cynthia", "Diana", "Vivian", "Esther", "Caroline", "Winnie", "Mary", "Christine", "Lydia", "Ann"]
        last_names = ["Otieno", "Kamau", "Mwangi", "Omondi", "Kipchoge", "Wanjiku", "Mutua", "Kiptoo", "Ochieng", "Maina", "Njoroge", "Kipkorir", "Chebet", "Anyango", "Mutiso"]

        counties = list(County.objects.all())
        
        students_created = 0
        with transaction.atomic():
            for i in range(1, 251):
                gender = random.choice(['M', 'F'])
                first_name = random.choice(first_names_m if gender == 'M' else first_names_f)
                last_name = random.choice(last_names)
                
                county = random.choice(counties)
                constituency = Constituency.objects.filter(county=county).first()
                ward = Ward.objects.filter(constituency=constituency).first() if constituency else None

                cls = created_classes[i % 9] 
                adm_num = f"NAI-2024{i:03d}"

                if not Student.objects.filter(admission_number=adm_num).exists():
                    Student.objects.create(
                        school=school,
                        admission_number=adm_num,
                        first_name=first_name,
                        last_name=last_name,
                        gender=gender,
                        class_level=cls.name,
                        county_fk=county,
                        constituency_fk=constituency,
                        ward_fk=ward,
                        guardian_name=f"Mr/Mrs {last_name}",
                        guardian_phone=f"0712{random.randint(100000, 999999)}",
                        is_active=True
                    )
                    students_created += 1

        self.stdout.write(self.style.SUCCESS(f"Successfully created {students_created} new students distributed across 9 classes!"))