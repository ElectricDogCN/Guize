package com.guize.bootstrap;

import com.fasterxml.jackson.databind.JsonNode;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.client.TestRestTemplate;
import org.springframework.http.ResponseEntity;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;

@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class BootstrapSmokeTest {
    @Autowired
    private TestRestTemplate http;

    @Test
    void startsWithoutConfiguredPlugins() {
        ResponseEntity<JsonNode> health = http.getForEntity("/actuator/health/readiness", JsonNode.class);
        assertEquals(200, health.getStatusCode().value());
        assertNotNull(health.getBody());
        assertEquals("UP", health.getBody().path("status").asText());
    }
}
