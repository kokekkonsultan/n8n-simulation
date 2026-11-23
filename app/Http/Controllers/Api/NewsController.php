<?php

namespace App\Http\Controllers\Api;

use App\Http\Controllers\Controller;
use App\Http\Requests\StoreNewsRequest;
use App\Http\Requests\UpdateNewsRequest;
use App\Http\Resources\NewsResource;
use App\Models\News;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Http\Resources\Json\AnonymousResourceCollection;

class NewsController extends Controller
{
    /**
     * Display a listing of the news.
     */
    public function index(Request $request): AnonymousResourceCollection
    {
        $query = News::query();

        // Search in title and content
        if ($search = $request->query('search')) {
            $query->where(function ($q) use ($search) {
                $q->where('title', 'like', "%{$search}%")
                  ->orWhere('content', 'like', "%{$search}%");
            });
        }

        // Filter by category
        if ($category = $request->query('category')) {
            $query->where('category', $category);
        }

        // Filter by status
        if ($status = $request->query('status')) {
            $query->where('status', $status);
        }

        // Sorting
        $allowedSorts = ['id', 'title', 'published_at', 'created_at', 'updated_at'];
        $sortBy = in_array($request->query('sort_by'), $allowedSorts, true)
            ? $request->query('sort_by')
            : 'created_at';

        $sortOrder = strtolower($request->query('order', 'desc')) === 'asc' ? 'asc' : 'desc';
        $query->orderBy($sortBy, $sortOrder);

        // Pagination
        $perPage = (int) $request->query('per_page', 10);
        $perPage = ($perPage > 0 && $perPage <= 100) ? $perPage : 10;

        $news = $query->paginate($perPage)->withQueryString();

        return NewsResource::collection($news);
    }

    /**
     * Store a newly created news in storage.
     */
    public function store(StoreNewsRequest $request): JsonResponse
    {
        $validated = $request->validated();

        if (empty($validated['slug'])) {
            $validated['slug'] = News::generateUniqueSlug($validated['title']);
        }

        if (($validated['status'] ?? 'draft') === 'published' && empty($validated['published_at'])) {
            $validated['published_at'] = now();
        }

        $news = News::create($validated);

        return response()->json([
            'success' => true,
            'message' => 'News created successfully',
            'data' => new NewsResource($news),
        ], 201);
    }

    /**
     * Display the specified news.
     */
    public function show(News $news): JsonResponse
    {
        return response()->json([
            'success' => true,
            'data' => new NewsResource($news),
        ]);
    }

    /**
     * Update the specified news in storage.
     */
    public function update(UpdateNewsRequest $request, News $news): JsonResponse
    {
        $validated = $request->validated();

        // If title changed and slug is not provided, regenerate slug
        if (isset($validated['title']) && empty($validated['slug']) && $validated['title'] !== $news->title) {
            $validated['slug'] = News::generateUniqueSlug($validated['title'], $news->id);
        }

        // If status changed to published and no published_at is set yet
        if (($validated['status'] ?? null) === 'published' && empty($news->published_at) && empty($validated['published_at'])) {
            $validated['published_at'] = now();
        }

        $news->update($validated);

        return response()->json([
            'success' => true,
            'message' => 'News updated successfully',
            'data' => new NewsResource($news->fresh()),
        ]);
    }

    /**
     * Remove the specified news from storage.
     */
    public function destroy(News $news): JsonResponse
    {
        $news->delete();

        return response()->json([
            'success' => true,
            'message' => 'News deleted successfully',
        ]);
    }
}
