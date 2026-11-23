<?php

namespace App\Http\Requests;

use Illuminate\Foundation\Http\FormRequest;
use Illuminate\Validation\Rule;

class UpdateStoreRequest extends FormRequest
{
    public function authorize(): bool
    {
        return true;
    }

    public function rules(): array
    {
        $store = $this->route('store');
        $storeId = is_object($store) ? $store->id : $store;

        return [
            'name' => ['sometimes', 'required', 'string', 'max:255'],
            'email' => [
                'sometimes',
                'required',
                'string',
                'email',
                'max:255',
                Rule::unique('stores', 'email')->ignore($storeId),
            ],
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
