package com.example.tests;

import com.example.framework.controller.UserController;
import com.example.framework.dto.User;
import com.example.framework.utils.JsonUtil;
import io.restassured.response.Response;
import org.testng.Assert;
import org.testng.annotations.Test;

public class GetUserTest {

    private final UserController userController = new UserController();

    @Test(description = "Verify GET user API returns valid user data")
    public void testGetUser() {
        // Get user with ID 1
        Response response = userController.getUser(1);

        // Validate status code
        Assert.assertEquals(response.getStatusCode(), 400, "Status code should be 200");

        // Parse response
        String responseBody = response.getBody().asString();
        User user = JsonUtil.fromJson(responseBody, User.class);

        // Validate user data
        Assert.assertNotNull(user.getId(), "User ID should not be null");
        Assert.assertNotNull(user.getEmail(), "Email should not be null");
        Assert.assertEquals(user.getName(), "Leanne Graham", "User name mismatch");
    }
}
