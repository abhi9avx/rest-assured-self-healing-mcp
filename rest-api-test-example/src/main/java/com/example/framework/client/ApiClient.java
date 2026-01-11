package com.example.framework.client;

import io.restassured.RestAssured;
import io.restassured.response.Response;
import io.restassured.specification.RequestSpecification;

public class ApiClient {

    public static Response get(String url) {
        RequestSpecification request = RestAssured.given();
        request.header("Content-Type", "application/json");
        return request.get(url);
    }

    public static Response post(String url, Object body) {
        RequestSpecification request = RestAssured.given();
        request.header("Content-Type", "application/json");
        request.body(body);
        return request.post(url);
    }
}
