from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.html import escape, mark_safe


class User(AbstractUser):
    is_student = models.BooleanField(default=False)
    is_teacher = models.BooleanField(default=False)


class Subject(models.Model):
    teacher = models.ForeignKey(User, on_delete=models.CASCADE, related_name='subjects')
    name = models.CharField(max_length=30)
    color = models.CharField(max_length=7, default='#007bff')

    def __str__(self):
        return self.name

    def get_html_badge(self):
        name = escape(self.name)
        color = escape(self.color)
        html = '<span class="badge badge-primary" style="background-color: %s">%s</span>' % (color, name)
        return mark_safe(html)


class Requirement(models.Model):
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='requirements')
    name = models.CharField(max_length=255)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='requirements')
    duedate = models.DateField()

    def __str__(self):
        return self.name


class Question(models.Model):
    requirement = models.ForeignKey(Requirement, on_delete=models.CASCADE, related_name='questions')
    text = models.CharField('Question', max_length=255)

    def __str__(self):
        return self.text


class Answer(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='answers')
    text = models.CharField('Answer', max_length=255)
    is_correct = models.BooleanField('Correct answer', default=False)

    def __str__(self):
        return self.text


class Student(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, primary_key=True)
    requirements = models.ManyToManyField(Requirement, through='TakenRequirement')
    subjects = models.ManyToManyField(Subject, related_name='subjected_students')

    def get_unanswered_questions(self, requirement):
        answered_questions = self.requirement_answers \
            .filter(answer__question__requirement=requirement) \
            .values_list('answer__question__pk', flat=True)
        questions = requirement.questions.exclude(pk__in=answered_questions).order_by('text')
        return questions

    def __str__(self):
        return self.user.username


class TakenRequirement(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='taken_requirements')
    requirement = models.ForeignKey(Requirement, on_delete=models.CASCADE, related_name='taken_requirements')
    score = models.FloatField()
    date = models.DateTimeField(auto_now_add=True)


class StudentAnswer(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='requirement_answers')
    answer = models.ForeignKey(Answer, on_delete=models.CASCADE, related_name='+')
