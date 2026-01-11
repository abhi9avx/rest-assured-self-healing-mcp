package com.example.framework.controller;

import com.example.framework.client.ApiClient;
import com.example.framework.config.ApiConfig;
import io.restassured.response.Response;

public class PostController {

    public Response getPost(int postId) {
        String url = ApiConfig.BASE_URL + ApiConfig.POSTS_ENDPOINT + "/" + postId;
        return ApiClient.get(url);
    }

    public Response createPost(Object postRequest) {
        String url = ApiConfig.BASE_URL + ApiConfig.POSTS_ENDPOINT;
        return ApiClient.post(url, postRequest);
    }
}
