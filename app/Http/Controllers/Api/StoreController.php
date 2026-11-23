<?php

namespace App\Http\Controllers\Api;

use App\Http\Controllers\Controller;
use App\Http\Requests\StoreStoreRequest;
use App\Http\Requests\UpdateStoreRequest;
use App\Http\Resources\StoreResource;
use App\Models\Store;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Http\Resources\Json\AnonymousResourceCollection;

class StoreController extends Controller
{
    /**
     * Display a listing of stores.
     */
    public function index(Request $request): AnonymousResourceCollection
    {
        $query = Store::query();

        // Search by store name or email
        if ($search = $request->query('search')) {
            $query->where(function ($q) use ($search) {
                $q->where('name', 'like', "%{$search}%")
                  ->orWhere('email', 'like', "%{$search}%");
            });
        }

        // Sorting
        $allowedSorts = ['id', 'name', 'email', 'created_at'];
        $sortBy = in_array($request->query('sort_by'), $allowedSorts, true)
            ? $request->query('sort_by')
            : 'created_at';

        $sortOrder = strtolower($request->query('order', 'desc')) === 'asc' ? 'asc' : 'desc';
        $query->orderBy($sortBy, $sortOrder);

        // Pagination
        $perPage = (int) $request->query('per_page', 10);
        $perPage = ($perPage > 0 && $perPage <= 100) ? $perPage : 10;

        $stores = $query->paginate($perPage)->withQueryString();

        return StoreResource::collection($stores);
    }

    /**
     * Store a newly created store in storage.
     */
    public function store(StoreStoreRequest $request): JsonResponse
    {
        $store = Store::create($request->validated());

        return response()->json([
            'success' => true,
            'message' => 'Data toko berhasil ditambahkan',
            'data' => new StoreResource($store),
        ], 201);
    }

    /**
     * Display the specified store.
     */
    public function show(Store $store): JsonResponse
    {
        return response()->json([
            'success' => true,
            'data' => new StoreResource($store),
        ]);
    }

    /**
     * Update the specified store in storage.
     */
    public function update(UpdateStoreRequest $request, Store $store): JsonResponse
    {
        $store->update($request->validated());

        return response()->json([
            'success' => true,
            'message' => 'Data toko berhasil diperbarui',
            'data' => new StoreResource($store->fresh()),
        ]);
    }

    /**
     * Remove the specified store from storage.
     */
    public function destroy(Store $store): JsonResponse
    {
        $store->delete();

        return response()->json([
            'success' => true,
            'message' => 'Data toko berhasil dihapus',
        ]);
    }
}
