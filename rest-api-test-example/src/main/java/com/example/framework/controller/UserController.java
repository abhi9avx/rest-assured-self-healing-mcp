package com.example.framework.controller;

import com.example.framework.client.ApiClient;
import com.example.framework.config.ApiConfig;
import io.restassured.response.Response;

public class UserController {

    public Response getUser(int userId) {
        String url = ApiConfig.BASE_URL + ApiConfig.USERS_ENDPOINT + "/" + userId;
        return ApiClient.get(url);
    }

    public Response getAllUsers() {
        String url = ApiConfig.BASE_URL + ApiConfig.USERS_ENDPOINT;
        return ApiClient.get(url);
    }
}
