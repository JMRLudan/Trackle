from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.views.generic import CreateView, ListView, UpdateView

from ..decorators import student_required
from ..forms import StudentSubjectsForm, StudentSignUpForm, TakeRequirementForm
from ..models import Requirement, Student, TakenRequirement, User
from datetime import datetime

class StudentSignUpView(CreateView):
    model = User
    form_class = StudentSignUpForm
    template_name = 'registration/signup_form.html'

    def get_context_data(self, **kwargs):
        kwargs['user_type'] = 'student'
        return super().get_context_data(**kwargs)

    def form_valid(self, form):
        user = form.save()
        login(self.request, user)
        return redirect('students:requirement_list')


@method_decorator([login_required, student_required], name='dispatch')
class StudentSubjectsView(UpdateView):
    model = Student
    form_class = StudentSubjectsForm
    template_name = 'reqs/students/subjects_form.html'
    success_url = reverse_lazy('students:requirement_list')

    def get_object(self):
        return self.request.user.student

    def form_valid(self, form):
        messages.success(self.request, 'Your subjects have been updated.')
        return super().form_valid(form)


@method_decorator([login_required, student_required], name='dispatch')
class RequirementListView(ListView):
    model = Requirement
    ordering = ('name', )
    context_object_name = 'requirements'
    template_name = 'reqs/students/requirement_list.html'

    def get_queryset(self):
        student = self.request.user.student
        student_subjects = student.subjects.values_list('pk', flat=True)
        queryset = Requirement.objects.filter(subject__in=student_subjects) \
                .exclude(duedate__lt=datetime.now().date()) \
                .order_by('duedate', 'name', 'subject')
        return queryset


@method_decorator([login_required, student_required], name='dispatch')
class TakenRequirementListView(ListView):
    model = TakenRequirement
    context_object_name = 'taken_requirements'
    template_name = 'reqs/students/finished_requirement_list.html'

    def get_queryset(self):
        queryset = self.request.user.student.taken_requirements \
            .select_related('requirement', 'requirement__subject') \
            .order_by('requirement__name')
        return queryset


@login_required
@student_required
def take_requirement(request, pk):
    requirement = get_object_or_404(Requirement, pk=pk)
    student = request.user.student

    if student.requirements.filter(pk=pk).exists():
        return render(request, 'students/taken_requirement.html')

    total_questions = requirement.questions.count()
    unanswered_questions = student.get_unanswered_questions(requirement)
    total_unanswered_questions = unanswered_questions.count()
    progress = 100 - round(((total_unanswered_questions - 1) / total_questions) * 100)
    question = unanswered_questions.first()

    if request.method == 'POST':
        form = TakeRequirementForm(question=question, data=request.POST)
        if form.is_valid():
            with transaction.atomic():
                student_answer = form.save(commit=False)
                student_answer.student = student
                student_answer.save()
                if student.get_unanswered_questions(requirement).exists():
                    return redirect('students:take_requirement', pk)
                else:
                    correct_answers = student.requirement_answers.filter(answer__question__requirement=requirement, answer__is_correct=True).count()
                    score = round((correct_answers / total_questions) * 100.0, 2)
                    TakenRequirement.objects.create(student=student, requirement=requirement, score=score)
                    if score < 50.0:
                        messages.warning(request, 'Better luck next time! Your score for the requirement %s was %s.' % (requirement.name, score))
                    else:
                        messages.success(request, 'Congratulations! You completed the requirement %s with success! You scored %s points.' % (requirement.name, score))
                    return redirect('students:requirement_list')
    else:
        form = TakeRequirementForm(question=question)

    return render(request, 'reqs/students/take_requirement_form.html', {
        'requirement': requirement,
        'question': question,
        'form': form,
        'progress': progress
    })
