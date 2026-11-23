<?php

use App\Models\Store;
use Illuminate\Foundation\Testing\RefreshDatabase;

uses(RefreshDatabase::class);

test('can fetch list of stores', function () {
    Store::create([
        'name' => 'Toko Berkah Jaya',
        'email' => 'berkah@example.com',
    ]);

    Store::create([
        'name' => 'Toko Maju Terus',
        'email' => 'maju@example.com',
    ]);

    $response = $this->getJson('/api/stores');

    $response->assertStatus(200)
        ->assertJsonStructure([
            'data' => [
                '*' => ['id', 'name', 'email', 'created_at', 'updated_at']
            ],
            'links',
            'meta',
        ])
        ->assertJsonCount(2, 'data');
});

test('can create a new store with name and email', function () {
    $payload = [
        'name' => 'Toko Elektronik Makmur',
        'email' => 'elektronik@makmur.com',
    ];

    $response = $this->postJson('/api/stores', $payload);

    $response->assertStatus(201)
        ->assertJsonPath('success', true)
        ->assertJsonPath('data.name', 'Toko Elektronik Makmur')
        ->assertJsonPath('data.email', 'elektronik@makmur.com');

    $this->assertDatabaseHas('stores', [
        'name' => 'Toko Elektronik Makmur',
        'email' => 'elektronik@makmur.com',
    ]);
});

test('fails validation when name or email is missing', function () {
    $response = $this->postJson('/api/stores', []);

    $response->assertStatus(422)
        ->assertJsonValidationErrors(['name', 'email']);
});

test('fails validation when email format is invalid or duplicate', function () {
    Store::create([
        'name' => 'Toko Pertama',
        'email' => 'duplikat@example.com',
    ]);

    // Invalid email format
    $responseInvalid = $this->postJson('/api/stores', [
        'name' => 'Toko Dua',
        'email' => 'bukan-email',
    ]);
    $responseInvalid->assertStatus(422)->assertJsonValidationErrors(['email']);

    // Duplicate email
    $responseDuplicate = $this->postJson('/api/stores', [
        'name' => 'Toko Tiga',
        'email' => 'duplikat@example.com',
    ]);
    $responseDuplicate->assertStatus(422)->assertJsonValidationErrors(['email']);
});

test('can get a single store by id', function () {
    $store = Store::create([
        'name' => 'Toko Serba Ada',
        'email' => 'serbaada@example.com',
    ]);

    $response = $this->getJson("/api/stores/{$store->id}");

    $response->assertStatus(200)
        ->assertJsonPath('success', true)
        ->assertJsonPath('data.id', $store->id)
        ->assertJsonPath('data.name', 'Toko Serba Ada')
        ->assertJsonPath('data.email', 'serbaada@example.com');
});

test('can update a store', function () {
    $store = Store::create([
        'name' => 'Toko Lama',
        'email' => 'lama@example.com',
    ]);

    $response = $this->putJson("/api/stores/{$store->id}", [
        'name' => 'Toko Baru',
        'email' => 'baru@example.com',
    ]);

    $response->assertStatus(200)
        ->assertJsonPath('success', true)
        ->assertJsonPath('data.name', 'Toko Baru')
        ->assertJsonPath('data.email', 'baru@example.com');

    $this->assertDatabaseHas('stores', [
        'id' => $store->id,
        'name' => 'Toko Baru',
        'email' => 'baru@example.com',
    ]);
});

test('can delete a store', function () {
    $store = Store::create([
        'name' => 'Toko Hapus',
        'email' => 'hapus@example.com',
    ]);

    $response = $this->deleteJson("/api/stores/{$store->id}");

    $response->assertStatus(200)
        ->assertJsonPath('success', true)
        ->assertJsonPath('message', 'Data toko berhasil dihapus');

    $this->assertDatabaseMissing('stores', [
        'id' => $store->id,
    ]);
});

test('can also access via api/shops alias endpoint', function () {
    $payload = [
        'name' => 'Shop Alias Test',
        'email' => 'alias@example.com',
    ];

    $response = $this->postJson('/api/shops', $payload);

    $response->assertStatus(201)
        ->assertJsonPath('success', true)
        ->assertJsonPath('data.name', 'Shop Alias Test');
});
