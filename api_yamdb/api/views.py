from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.db.models import Avg
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, mixins, permissions, status, viewsets
from rest_framework.generics import CreateAPIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from api.filters import TitleFilter
from api.permissions import (IsAdminUser, IsModeratorIsAdminOrReadonly,
                             IsOwner, IsOwnerIsModeratorIsAdminOrReadOnly)
from api.serializers import (CategorySerializer, CommentSerializer,
                             CustomTokenCodeValidate, CustomTokenDateNotNull,
                             CustomUserSerializer, GenreSerializer,
                             ReviewPatchSerializer, ReviewSerializer,
                             TitleSafeRequestSerializer,
                             TitleUnsafeRequestSerializer,
                             UserProfileSerializer, UserSerializer)
from reviews.models import Category, CustomUser, Genre, Review, Title


class ListCreateDeleteModelViewSet(mixins.ListModelMixin,
                                   mixins.CreateModelMixin,
                                   mixins.DestroyModelMixin,
                                   viewsets.GenericViewSet):
    pass


class CommentViewSet(viewsets.ModelViewSet):
    """
    Класс-обработчик API-запросов к комментариям к отзывам на произведения.
    """
    serializer_class = CommentSerializer
    permission_classes = (IsOwnerIsModeratorIsAdminOrReadOnly,)
    http_method_names = ('get', 'post', 'patch', 'delete',)

    def get_review(self):
        review_id = self.kwargs.get('review_id')
        title_id = self.kwargs.get('title_id')
        return get_object_or_404(Review, id=review_id, title_id=title_id)

    def get_queryset(self):
        review = self.get_review()
        return review.comments_for_review.all()

    def perform_create(self, serializer):
        review = self.get_review()
        serializer.save(review=review,
                        author=self.request.user)


class ReviewViewSet(viewsets.ModelViewSet):
    """
    Класс-обработчик API-запросов к отзывам на произведения.
    """
    permission_classes = (IsOwnerIsModeratorIsAdminOrReadOnly,)
    http_method_names = ['get', 'post', 'patch', 'delete']

    def get_title(self):
        title_id = self.kwargs.get('title_id')
        return get_object_or_404(Title, id=title_id)

    def get_queryset(self):
        title = self.get_title()
        return title.reviews_for_title.all()

    def perform_create(self, serializer):
        title = self.get_title()
        serializer.save(title=title,
                        author=self.request.user)

    def get_serializer_class(self):
        if self.action == 'partial_update':
            return ReviewPatchSerializer
        return ReviewSerializer


class CategoryViewSet(ListCreateDeleteModelViewSet):
    """
    Класс-обработчик API-запросов к категориям произведений.
    """
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    filter_backends = (filters.SearchFilter,)
    search_fields = ('name',)
    lookup_field = 'slug'
    permission_classes = (IsModeratorIsAdminOrReadonly,)


class GenreViewSet(ListCreateDeleteModelViewSet):
    """
    Класс-обработчик API-запросов к жанрам произведений.
    """
    queryset = Genre.objects.all()
    serializer_class = GenreSerializer
    filter_backends = (filters.SearchFilter,)
    search_fields = ('name',)
    lookup_field = 'slug'
    permission_classes = (IsModeratorIsAdminOrReadonly,)


class TitleViewSet(viewsets.ModelViewSet):
    """
    Класс-обработчик API-запросов произведениям.
    """
    queryset = Title.objects.annotate(rating=Avg('reviews_for_title__score'))
    http_method_names = ('get', 'post', 'patch', 'delete',)
    filter_backends = (DjangoFilterBackend,)
    filterset_class = TitleFilter
    permission_classes = (IsModeratorIsAdminOrReadonly,)

    def get_serializer_class(self):
        """
        Переопределение стандартного метода.
        В зависимости от метода запроса
        используется соответствующий сериализатор.
        """
        if self.request.method in permissions.SAFE_METHODS:
            return TitleSafeRequestSerializer
        return TitleUnsafeRequestSerializer


class UserSignUpView(CreateAPIView):
    """
    Класс-создатель нового пользователя.
    """
    queryset = CustomUser.objects.all()
    serializer_class = CustomUserSerializer
    permission_classes = (AllowAny,)

    def create(self, request, *args, **kwargs):
        if CustomUser.objects.filter(
                username=request.data.get('username'),
                email=request.data.get('email')):
            return Response(
                {'message': 'Пользователь уже зарегистрирован'},
                status=status.HTTP_200_OK
            )
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        username = serializer.validated_data['username']
        email = serializer.validated_data['email']
        user = serializer.save()
        confirmation_code = default_token_generator.make_token(user)
        user.confirmation_code = confirmation_code
        user.save()
        send_mail(
            'Confirmation Code',
            f'Your confirmation code: {confirmation_code}',
            from_email=('from@' + settings.DOMAIN_NAME),
            recipient_list=[email],
            fail_silently=False,)
        return Response({
            'username': username,
            'email': email
        }, status=status.HTTP_200_OK)


class CustomTokenObtainPairView(CreateAPIView):
    """
    Класс-создатель JWTToken по username и confirmation_code.
    """
    queryset = CustomUser.objects.all()
    permission_classes = (AllowAny,)

    def create(self, request, *args, **kwargs):
        serializer = CustomTokenDateNotNull(data=request.data)
        if serializer.is_valid():
            user = get_object_or_404(
                CustomUser, username=serializer.validated_data['username'])
            serializer = CustomTokenCodeValidate(user, data=request.data)
            if serializer.is_valid():
                refresh = RefreshToken.for_user(user=user)
                access_token = str(refresh.access_token)
                return Response(
                    {'token': access_token}, status=status.HTTP_200_OK)
        return Response(
            {'error': 'Проверьте корректность введеных данных'},
            status=status.HTTP_400_BAD_REQUEST)


class UserProfileView(APIView):
    """
    Класс-обработчик API-запросов к профилю пользователя.
    """
    permission_classes = (IsOwner, IsAuthenticated)

    def get(self, request):
        user = request.user
        serializer = UserProfileSerializer(user)
        return Response(serializer.data)

    def patch(self, request):
        user = request.user
        serializer = UserProfileSerializer(
            user,
            data=request.data,
            partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.validated_data, status=status.HTTP_200_OK)


class UserViewSet(viewsets.ModelViewSet):
    """
    Класс-обработчик API-запросов от администратора.
    """
    queryset = CustomUser.objects.all()
    serializer_class = UserSerializer
    permission_classes = (IsAdminUser,)
    filter_backends = (filters.SearchFilter,)
    search_fields = ('username',)
    lookup_field = 'username'

    def create(self, request, *args, **kwargs):
        username = request.data.get('username')
        email = request.data.get('email')
        existing_user = CustomUser.objects.filter(
            username=username,
            email=email
        ).exists()
        if existing_user:
            return Response(status=status.HTTP_200_OK)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(data=request.data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        return Response(status=status.HTTP_405_METHOD_NOT_ALLOWED)

    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(
            instance,
            data=request.data,
            partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset()).order_by('id')
        paginator = PageNumberPagination()
        paginator.page_size = 5
        result_page = paginator.paginate_queryset(queryset, request)
        serializer = self.get_serializer(result_page, many=True)
        return paginator.get_paginated_response(serializer.data)
