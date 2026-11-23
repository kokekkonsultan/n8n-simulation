<?php

use App\Http\Controllers\Api\NewsController;
use App\Http\Controllers\Api\StoreController;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Route;

/*
|--------------------------------------------------------------------------
| API Routes
|--------------------------------------------------------------------------
*/

Route::get('/user', function (Request $request) {
    return $request->user();
})->middleware('auth:sanctum');

Route::apiResource('news', NewsController::class);
Route::apiResource('stores', StoreController::class);
Route::apiResource('shops', StoreController::class)->parameters(['shops' => 'store']);
