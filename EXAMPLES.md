# Self-Healing Agent - Failure Examples

This document demonstrates the agent's capability to handle diverse failure types in enterprise-scale automation frameworks.

## 1. AssertionError - Status Code Mismatch

**Scenario**: API returns `200 OK` but test expects `500 Internal Server Error`.

**Original Code**:
```java
@Test
public void verifyCreatePost() {
    Response response = postController.createPost(request);
    Assert.assertEquals(response.getStatusCode(), 500); // WRONG
}
```

**Agent Action**:
- Detects: `AssertionError: expected [500] but found [200]`
- Analyzes: API is working correctly, test expectation is wrong
- Fixes: Changes assertion to `200`

**Fixed Code**:
```java
Assert.assertEquals(response.getStatusCode(), 200); // FIXED
```

---

## 2. NullPointerException - Missing Null Check

**Scenario**: Accessing a field on a null object.

**Original Code**:
```java
@Test
public void verifyUserData() {
    UserResponse user = userClient.getUser(999); // Non-existent user
    Assert.assertNotNull(user.getEmail()); // NPE here
}
```

**Agent Action**:
- Detects: `NullPointerException at line 45`
- Analyzes: `user` object is null before accessing `.getEmail()`
- Fixes: Adds null check

**Fixed Code**:
```java
Assert.assertNotNull(user, "User should not be null");
Assert.assertNotNull(user.getEmail());
```

---

## 3. NoSuchElementException - Incorrect Locator

**Scenario**: UI element locator is outdated.

**Original Code**:
```java
@Test
public void clickLoginButton() {
    driver.findElement(By.id("old-login-btn")).click(); // Element doesn't exist
}
```

**Agent Action**:
- Detects: `NoSuchElementException: Unable to locate element: #old-login-btn`
- Analyzes: Locator ID has changed
- Fixes: Updates to new ID (if found in page source or suggests common alternatives)

**Fixed Code**:
```java
driver.findElement(By.id("login-btn")).click(); // Updated ID
```

---

## 4. TimeoutException - Insufficient Wait

**Scenario**: Element takes longer to load than expected.

**Original Code**:
```java
@Test
public void waitForDashboard() {
    WebDriverWait wait = new WebDriverWait(driver, Duration.ofSeconds(5));
    wait.until(ExpectedConditions.visibilityOfElementLocated(By.id("dashboard")));
}
```

**Agent Action**:
- Detects: `TimeoutException: Timed out after 5 seconds`
- Analyzes: Wait time is too short
- Fixes: Increases timeout

**Fixed Code**:
```java
WebDriverWait wait = new WebDriverWait(driver, Duration.ofSeconds(30)); // Increased
```

---

## 5. JsonParseException - DTO Field Mismatch

**Scenario**: API response field name doesn't match DTO.

**Original Code**:
```java
public class UserDTO {
    private String userName; // API returns "username" (lowercase)
}
```

**Agent Action**:
- Detects: `JsonParseException: Unrecognized field "username"`
- Analyzes: Field naming mismatch
- Fixes: Updates DTO field or adds `@JsonProperty` annotation

**Fixed Code**:
```java
@JsonProperty("username")
private String userName;
```

---

## 6. ArrayIndexOutOfBoundsException - List Access

**Scenario**: Accessing an index that doesn't exist.

**Original Code**:
```java
@Test
public void verifyFirstPost() {
    List<Post> posts = postClient.getAllPosts();
    Assert.assertNotNull(posts.get(0).getTitle()); // List might be empty
}
```

**Agent Action**:
- Detects: `ArrayIndexOutOfBoundsException: Index 0 out of bounds for length 0`
- Analyzes: List is empty
- Fixes: Adds size check

**Fixed Code**:
```java
Assert.assertTrue(posts.size() > 0, "Posts list should not be empty");
Assert.assertNotNull(posts.get(0).getTitle());
```

---

## How to Test These Scenarios

1. **Introduce a failure** in your test suite (e.g., change a status code assertion).
2. **Run the agent**:
   ```bash
   ./run_agent.sh --repo your-repo --test-filter YourTestClass
   ```
3. **Observe** the agent detect, analyze, and fix the issue.
4. **Verify** the fix by checking the re-run results.

---

## Enterprise Framework Support

The agent is designed to handle:
- **Complex folder structures**: Multi-module Maven/Gradle projects
- **Nested packages**: Deep package hierarchies (e.g., `com.company.product.module.tests`)
- **Multiple source roots**: `src/test/java`, `src/main/java`, custom test directories
- **Large codebases**: Efficient file discovery with directory filtering

The enhanced file discovery algorithm uses 4 strategies:
1. Direct absolute path lookup
2. Relative path from repo root
3. Common test directory search
4. Full repository walk (with `.git`, `node_modules`, `build` exclusions)
