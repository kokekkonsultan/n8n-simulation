<?php

use App\Models\News;
use Illuminate\Foundation\Testing\RefreshDatabase;

uses(RefreshDatabase::class);

test('can fetch list of news', function () {
    News::create([
        'title' => 'First News',
        'content' => 'First content',
        'category' => 'Technology',
        'status' => 'published',
    ]);

    News::create([
        'title' => 'Second News',
        'content' => 'Second content',
        'category' => 'Sports',
        'status' => 'draft',
    ]);

    $response = $this->getJson('/api/news');

    $response->assertStatus(200)
        ->assertJsonStructure([
            'data' => [
                '*' => ['id', 'title', 'slug', 'content', 'category', 'status', 'published_at', 'created_at', 'updated_at']
            ],
            'links',
            'meta',
        ])
        ->assertJsonCount(2, 'data');
});

test('can filter news by category and status', function () {
    News::create([
        'title' => 'Tech News',
        'content' => 'Tech content',
        'category' => 'Technology',
        'status' => 'published',
    ]);

    News::create([
        'title' => 'Sports News',
        'content' => 'Sports content',
        'category' => 'Sports',
        'status' => 'draft',
    ]);

    $response = $this->getJson('/api/news?category=Technology&status=published');

    $response->assertStatus(200)
        ->assertJsonCount(1, 'data')
        ->assertJsonPath('data.0.title', 'Tech News');
});

test('can create a news item with auto-generated slug', function () {
    $payload = [
        'title' => 'Breaking News: AI Development',
        'content' => 'This is full news content for testing.',
        'category' => 'Technology',
        'author' => 'Editor',
        'status' => 'published',
    ];

    $response = $this->postJson('/api/news', $payload);

    $response->assertStatus(201)
        ->assertJsonPath('success', true)
        ->assertJsonPath('data.title', 'Breaking News: AI Development')
        ->assertJsonPath('data.slug', 'breaking-news-ai-development')
        ->assertJsonPath('data.status', 'published');

    $this->assertDatabaseHas('news', [
        'title' => 'Breaking News: AI Development',
        'slug' => 'breaking-news-ai-development',
    ]);
});

test('fails validation when creating news without required fields', function () {
    $response = $this->postJson('/api/news', []);

    $response->assertStatus(422)
        ->assertJsonValidationErrors(['title', 'content']);
});

test('can get a single news by id', function () {
    $news = News::create([
        'title' => 'Single News Item',
        'content' => 'Single news content',
    ]);

    $response = $this->getJson("/api/news/{$news->id}");

    $response->assertStatus(200)
        ->assertJsonPath('success', true)
        ->assertJsonPath('data.id', $news->id)
        ->assertJsonPath('data.title', 'Single News Item');
});

test('returns 404 if news not found', function () {
    $response = $this->getJson('/api/news/99999');

    $response->assertStatus(404);
});

test('can update a news item', function () {
    $news = News::create([
        'title' => 'Original Title',
        'content' => 'Original Content',
    ]);

    $updatePayload = [
        'title' => 'Updated Title',
        'content' => 'Updated Content',
        'status' => 'published',
    ];

    $response = $this->putJson("/api/news/{$news->id}", $updatePayload);

    $response->assertStatus(200)
        ->assertJsonPath('success', true)
        ->assertJsonPath('data.title', 'Updated Title')
        ->assertJsonPath('data.content', 'Updated Content')
        ->assertJsonPath('data.status', 'published');

    $this->assertDatabaseHas('news', [
        'id' => $news->id,
        'title' => 'Updated Title',
    ]);
});

test('can delete a news item', function () {
    $news = News::create([
        'title' => 'To Be Deleted',
        'content' => 'Content here',
    ]);

    $response = $this->deleteJson("/api/news/{$news->id}");

    $response->assertStatus(200)
        ->assertJsonPath('success', true)
        ->assertJsonPath('message', 'News deleted successfully');

    $this->assertDatabaseMissing('news', [
        'id' => $news->id,
    ]);
});
