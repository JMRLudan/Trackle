from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Avg, Count
from django.forms import inlineformset_factory
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils.decorators import method_decorator
from django.views.generic import (CreateView, DeleteView, DetailView, ListView,
                                  UpdateView)

from ..decorators import teacher_required
from ..forms import BaseAnswerInlineFormSet, QuestionForm, TeacherSignUpForm, RequirementForm
from ..models import Answer, Question, Requirement, User, Subject


class TeacherSignUpView(CreateView):
    model = User
    form_class = TeacherSignUpForm
    template_name = 'registration/signup_form.html'

    def get_context_data(self, **kwargs):
        kwargs['user_type'] = 'teacher'
        return super().get_context_data(**kwargs)

    def form_valid(self, form):
        user = form.save()
        login(self.request, user)
        return redirect('teachers:req_change_list')


@method_decorator([login_required, teacher_required], name='dispatch')
class RequirementListView(ListView):
    model = Requirement
    ordering = ('name', )
    context_object_name = 'requirements'
    template_name = 'reqs/teachers/req_change_list.html'

    def get_queryset(self):
        queryset = self.request.user.requirements \
            .select_related('subject') \
            .order_by('duedate', 'name', 'subject')
        return queryset

@method_decorator([login_required, teacher_required], name='dispatch')
class SubjectCreateView(CreateView):
    model = Subject
    fields = ('name',)
    template_name = 'reqs/teachers/sub_add_form.html'

    def form_valid(self, form):
        subject = form.save(commit=False)
        subject.teacher = self.request.user
        subject.save()
        messages.success(self.request, 'The subject was successfully created!')
        return redirect('teachers:req_change_list')

@method_decorator([login_required, teacher_required], name='dispatch')
class RequirementCreateView(CreateView):
    model = Requirement
    form_class = RequirementForm
    template_name = 'reqs/teachers/req_add_form.html'

    def get_form_kwargs(self):
        kwargs = super(RequirementCreateView, self).get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        requirement = form.save(commit=False)
        requirement.owner = self.request.user
        requirement.save()
        messages.success(self.request, 'The requirement was successfully created!')
        return redirect('teachers:requirement_change', requirement.pk)


@method_decorator([login_required, teacher_required], name='dispatch')
class RequirementUpdateView(UpdateView):
    model = Requirement
    fields = ('name', 'subject', )
    context_object_name = 'requirement'
    template_name = 'reqs/teachers/requirement_change_form.html'

    def get_context_data(self, **kwargs):
        kwargs['questions'] = self.get_object().questions.annotate(answers_count=Count('answers'))
        return super().get_context_data(**kwargs)

    def get_queryset(self):
        '''
        This method is an implicit object-level permission management
        This view will only match the ids of existing requirements that belongs
        to the logged in user.
        '''
        return self.request.user.requirements.all()

    def get_success_url(self):
        return reverse('teachers:requirement_change', kwargs={'pk': self.object.pk})


@method_decorator([login_required, teacher_required], name='dispatch')
class RequirementDeleteView(DeleteView):
    model = Requirement
    context_object_name = 'requirement'
    template_name = 'reqs/teachers/requirement_delete_confirm.html'
    success_url = reverse_lazy('teachers:req_change_list')

    def delete(self, request, *args, **kwargs):
        requirement = self.get_object()
        messages.success(request, 'The requirement %s was successfully deleted!' % requirement.name)
        return super().delete(request, *args, **kwargs)

    def get_queryset(self):
        return self.request.user.requirements.all()

@login_required
@teacher_required
def question_add(request, pk):
    # By filtering the requirement by the url keyword argument `pk` and
    # by the owner, which is the logged in user, we are protecting
    # this view at the object-level. Meaning only the owner of
    # requirement will be able to add questions to it.
    requirement = get_object_or_404(Requirement, pk=pk, owner=request.user)

    if request.method == 'POST':
        form = QuestionForm(request.POST)
        if form.is_valid():
            question = form.save(commit=False)
            question.requirement = requirement
            question.save()
            messages.success(request, 'You may now add answers/options to the question.')
            return redirect('teachers:question_change', requirement.pk, question.pk)
    else:
        form = QuestionForm()

    return render(request, 'reqs/teachers/question_add_form.html', {'requirement': requirement, 'form': form})


@login_required
@teacher_required
def question_change(request, requirement_pk, question_pk):
    # Simlar to the `question_add` view, this view is also managing
    # the permissions at object-level. By querying both `requirement` and
    # `question` we are making sure only the owner of the requirement can
    # change its details and also only questions that belongs to this
    # specific requirement can be changed via this url (in cases where the
    # user might have forged/player with the url params.
    requirement = get_object_or_404(Requirement, pk=requirement_pk, owner=request.user)
    question = get_object_or_404(Question, pk=question_pk, requirement=requirement)

    AnswerFormSet = inlineformset_factory(
        Question,  # parent model
        Answer,  # base model
        formset=BaseAnswerInlineFormSet,
        fields=('text', 'is_correct'),
        min_num=2,
        validate_min=True,
        max_num=10,
        validate_max=True
    )

    if request.method == 'POST':
        form = QuestionForm(request.POST, instance=question)
        formset = AnswerFormSet(request.POST, instance=question)
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                form.save()
                formset.save()
            messages.success(request, 'Question and answers saved with success!')
            return redirect('teachers:requirement_change', requirement.pk)
    else:
        form = QuestionForm(instance=question)
        formset = AnswerFormSet(instance=question)

    return render(request, 'reqs/teachers/question_change_form.html', {
        'requirement': requirement,
        'question': question,
        'form': form,
        'formset': formset
    })


@method_decorator([login_required, teacher_required], name='dispatch')
class QuestionDeleteView(DeleteView):
    model = Question
    context_object_name = 'question'
    template_name = 'reqs/teachers/question_delete_confirm.html'
    pk_url_kwarg = 'question_pk'

    def get_context_data(self, **kwargs):
        question = self.get_object()
        kwargs['requirement'] = question.requirement
        return super().get_context_data(**kwargs)

    def delete(self, request, *args, **kwargs):
        question = self.get_object()
        messages.success(request, 'The question %s was deleted with success!' % question.text)
        return super().delete(request, *args, **kwargs)

    def get_queryset(self):
        return Question.objects.filter(requirement__owner=self.request.user)

    def get_success_url(self):
        question = self.get_object()
        return reverse('teachers:requirement_change', kwargs={'pk': question.requirement_id})
