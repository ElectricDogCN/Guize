package com.guize.bootstrap;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.client.TestRestTemplate;
import org.springframework.http.ResponseEntity;
import org.springframework.test.util.ReflectionTestUtils;

import java.nio.file.Path;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

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

    @Test
    void readyEventAfterClosingCannotStartAnAssessment(@TempDir Path directory) throws Exception {
        PluginRegistry registry = new PluginRegistry(new ObjectMapper(), directory.toString(), ".",
                directory.resolve("unavailable-interpreter").toString(), "1000");
        CountDownLatch callbackScheduled = new CountDownLatch(1);
        CountDownLatch deliverReadyEvent = new CountDownLatch(1);
        CompletableFuture<Void> ready = CompletableFuture.runAsync(() -> {
            callbackScheduled.countDown();
            try {
                if (!deliverReadyEvent.await(5, TimeUnit.SECONDS)) {
                    throw new AssertionError("Ready callback was never released");
                }
                registry.loadConfiguredPlugins();
            } catch (InterruptedException error) {
                Thread.currentThread().interrupt();
                throw new AssertionError(error);
            }
        });

        try {
            assertTrue(callbackScheduled.await(5, TimeUnit.SECONDS));
            registry.stopLoading();
        } finally {
            deliverReadyEvent.countDown();
        }
        ready.get(5, TimeUnit.SECONDS);
        assertNull(ReflectionTestUtils.getField(registry, "loader"));
    }
}
