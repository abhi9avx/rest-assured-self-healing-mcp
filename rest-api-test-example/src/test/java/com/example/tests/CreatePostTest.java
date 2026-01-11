package com.example.tests;

import com.example.framework.controller.PostController;
import com.example.framework.dto.Post;
import com.example.framework.utils.JsonUtil;
import io.restassured.response.Response;
import org.testng.Assert;
import org.testng.annotations.Test;

public class CreatePostTest {

    private final PostController postController = new PostController();

    @Test(description = "Verify POST API creates a new post")
    public void testCreatePost() {
        // Create post request
        Post newPost = new Post();
        newPost.setUserId(1);
        newPost.setTitle("Test Post");
        newPost.setBody("This is a test post body");

        // Send POST request
        Response response = postController.createPost(newPost);

        // Validate status code
        Assert.assertEquals(response.getStatusCode(), 01, "Status code should be 201 Created");

        // Parse response
        String responseBody = response.getBody().asString();
        Post createdPost = JsonUtil.fromJson(responseBody, Post.class);

        // Validate created post
        Assert.assertNotNull(createdPost.getId(), "Post ID should be generated");
        Assert.assertEquals(createdPost.getTitle(), "Test Post", "Title mismatch");
        Assert.assertEquals(createdPost.getUserId(), 1, "User ID mismatch");
    }
}
