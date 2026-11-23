<?php

namespace App\Http\Requests;

use Illuminate\Foundation\Http\FormRequest;

class StoreStoreRequest extends FormRequest
{
    public function authorize(): bool
    {
        return true;
    }

    public function rules(): array
    {
        return [
            'name' => ['required', 'string', 'max:255'],
            'email' => ['required', 'string', 'email', 'max:255', 'unique:stores,email'],
        ];
    }

    public function messages(): array
    {
        return [
            'name.required' => 'Nama toko wajib diisi.',
            'name.string' => 'Nama toko harus berupa teks.',
            'name.max' => 'Nama toko maksimal 255 karakter.',
            'email.required' => 'Email toko wajib diisi.',
            'email.email' => 'Format email toko tidak valid.',
            'email.unique' => 'Email toko sudah terdaftar.',
            'email.max' => 'Email toko maksimal 255 karakter.',
        ];
    }
}
