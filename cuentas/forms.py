from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth import authenticate
from django.contrib.auth.decorators import user_passes_test
from .models import Usuario

class FormularioLogin(AuthenticationForm):
    """
    Formulario personalizado para el login
    Acepta username o email como identificador.
    """
    username = forms.CharField(
        label="Usuario o correo electrónico",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'usuario o tu@email.com',
            'autofocus': True
        })
    )
    password = forms.CharField(
        label="Contraseña",
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Tu contraseña'
        })
    )

    def clean(self):
        identifier = self.cleaned_data.get('username')
        password = self.cleaned_data.get('password')

        if identifier and password:
            # Buscar usuario por email o username
            try:
                if '@' in identifier:
                    user = Usuario.objects.get(email=identifier)
                else:
                    user = Usuario.objects.get(username=identifier)
                self.user_cache = authenticate(
                    self.request,
                    username=user.email,
                    password=password
                )
                if self.user_cache is None:
                    raise forms.ValidationError(
                        "Credenciales inválidas. Verifica tus datos.",
                        code='invalid_login',
                    )
            except Usuario.DoesNotExist:
                raise forms.ValidationError(
                    "Credenciales inválidas. Verifica tus datos.",
                    code='invalid_login',
                )
        return self.cleaned_data

class FormularioRegistro(UserCreationForm):
    """
    Formulario personalizado para el registro
    """
    email = forms.EmailField(
        label="Correo electrónico",
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'tu@email.com'
        })
    )
    first_name = forms.CharField(
        label="Nombre",
        max_length=30,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Tu nombre'
        })
    )
    last_name = forms.CharField(
        label="Apellido",
        max_length=30,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Tu apellido'
        })
    )
    password1 = forms.CharField(
        label="Contraseña",
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Mínimo 8 caracteres'
        })
    )
    password2 = forms.CharField(
        label="Confirmar contraseña",
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Repite tu contraseña'
        })
    )

    class Meta:
        model = Usuario
        fields = ('email', 'first_name', 'last_name', 'password1', 'password2')

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if Usuario.objects.filter(email=email).exists():
            raise forms.ValidationError("Ya existe una cuenta con este correo electrónico.")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        # Asegurar que la contraseña quede hasheada correctamente
        user.set_password(self.cleaned_data['password1'])
        
        # Generar username único basado en el email
        base_username = user.email.split('@')[0]
        username = base_username
        counter = 1
        while Usuario.objects.filter(username=username).exists():
            username = f"{base_username}{counter}"
            counter += 1
        user.username = username
        
        if commit:
            user.save()
        return user

class FormularioCrearUsuario(forms.ModelForm):
    """
    Formulario para que los administradores creen usuarios
    """
    password1 = forms.CharField(
        label="Contraseña",
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Mínimo 8 caracteres'
        }),
        help_text="La contraseña debe tener al menos 8 caracteres."
    )
    password2 = forms.CharField(
        label="Confirmar contraseña",
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Repite la contraseña'
        })
    )

    class Meta:
        model = Usuario
        fields = ('email', 'first_name', 'last_name', 'is_active', 'is_staff')
        widgets = {
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'usuario@ejemplo.com'
            }),
            'first_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nombre del usuario'
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Apellido del usuario'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'is_staff': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
        }

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if Usuario.objects.filter(email=email).exists():
            raise forms.ValidationError("Ya existe una cuenta con este correo electrónico.")
        return email

    def clean_password2(self):
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError("Las contraseñas no coinciden.")
        return password2

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        
        # Generar username único basado en el email
        base_username = user.email.split('@')[0]
        username = base_username
        counter = 1
        while Usuario.objects.filter(username=username).exists():
            username = f"{base_username}{counter}"
            counter += 1
        user.username = username
        
        if commit:
            user.save()
        return user

class FormularioEditarUsuario(forms.ModelForm):
    """
    Formulario para editar usuarios existentes
    """
    class Meta:
        model = Usuario
        fields = ('username', 'email', 'first_name', 'last_name', 'is_active', 'is_staff')
        widgets = {
            'username': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'usuario'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'usuario@ejemplo.com'
            }),
            'first_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nombre del usuario'
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Apellido del usuario'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'is_staff': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
        }

    def clean_email(self):
        email = self.cleaned_data.get('email')
        # Verificar que el email no esté en uso por otro usuario
        if Usuario.objects.filter(email=email).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("Ya existe una cuenta con este correo electrónico.")
        return email

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if Usuario.objects.filter(username=username).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("Ya existe una cuenta con este usuario.")
        return username

class FormularioCambiarContraseña(forms.Form):
    """
    Formulario para cambiar la contraseña de un usuario
    """
    password1 = forms.CharField(
        label="Nueva contraseña",
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Mínimo 8 caracteres'
        }),
        help_text="La contraseña debe tener al menos 8 caracteres."
    )
    password2 = forms.CharField(
        label="Confirmar nueva contraseña",
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Repite la contraseña'
        })
    )

    def clean_password2(self):
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError("Las contraseñas no coinciden.")
        return password2