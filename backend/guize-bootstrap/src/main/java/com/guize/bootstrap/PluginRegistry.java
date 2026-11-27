package com.guize.bootstrap;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.JsonNodeFactory;
import jakarta.annotation.PreDestroy;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.actuate.health.Health;
import org.springframework.boot.actuate.health.HealthIndicator;
import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.context.event.EventListener;
import org.springframework.stereotype.Component;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.concurrent.TimeUnit;

@Component
final class PluginRegistry implements HealthIndicator {
    private static final Logger LOG = LoggerFactory.getLogger(PluginRegistry.class);
    private static final long ASSESSMENT_TIMEOUT_SECONDS = 20;

    private final ObjectMapper mapper;
    private final String directory;
    private final String repository;
    private final String python;
    private final String timeoutMillis;
    private volatile JsonNode plugins = JsonNodeFactory.instance.objectNode();
    private Thread loader;
    private boolean closed;

    PluginRegistry(ObjectMapper mapper,
                   @Value("${guize.bootstrap.plugin-directory:}") String directory,
                   @Value("${guize.bootstrap.repository-root:.}") String repository,
                   @Value("${guize.bootstrap.python:python}") String python,
                   @Value("${guize.bootstrap.probe-timeout-millis:1000}") String timeoutMillis) {
        this.mapper = mapper;
        this.directory = directory;
        this.repository = repository;
        this.python = python;
        this.timeoutMillis = timeoutMillis;
    }

    @EventListener(ApplicationReadyEvent.class)
    synchronized void loadConfiguredPlugins() {
        if (closed || loader != null || directory.isBlank()) {
            return;
        }
        loader = new Thread(this::assessPlugins, "guize-plugin-startup");
        loader.setDaemon(true);
        loader.start();
    }

    private void assessPlugins() {
        Path output = null;
        Process process = null;
        boolean interrupted = false;
        try {
            Path root = Path.of(repository).toAbsolutePath();
            Path assessor = root.resolve("backend/guize-bootstrap/plugin_probe.py");
            output = Files.createTempFile("guize-plugin-assessment-", ".json");
            process = new ProcessBuilder(python, "-B", assessor.toString(), root.toString(),
                    Path.of(directory).toAbsolutePath().toString(), timeoutMillis)
                    .redirectOutput(output.toFile())
                    .redirectError(ProcessBuilder.Redirect.DISCARD)
                    .start();
            if (!process.waitFor(ASSESSMENT_TIMEOUT_SECONDS, TimeUnit.SECONDS) || process.exitValue() != 0) {
                LOG.warn("Optional plugin assessment did not complete successfully");
                return;
            }
            JsonNode assessment = mapper.readTree(output.toFile());
            if (assessment == null || !assessment.path("coreMayStart").asBoolean()
                    || !assessment.path("plugins").isObject()) {
                LOG.warn("Optional plugin assessment returned an invalid result");
                return;
            }
            plugins = assessment.path("plugins");
        } catch (IOException | IllegalArgumentException error) {
            LOG.warn("Optional plugin assessment could not start");
        } catch (InterruptedException error) {
            interrupted = true;
        } finally {
            if (process != null && process.isAlive()) {
                process.destroyForcibly();
                try {
                    process.waitFor(2, TimeUnit.SECONDS);
                } catch (InterruptedException error) {
                    interrupted = true;
                }
            }
            if (output != null) {
                try {
                    Files.deleteIfExists(output);
                } catch (IOException error) {
                    LOG.warn("Could not remove the optional plugin assessment output");
                }
            }
            if (interrupted) {
                Thread.currentThread().interrupt();
            }
        }
    }

    @PreDestroy
    void stopLoading() {
        Thread current;
        synchronized (this) {
            closed = true;
            current = loader;
        }
        if (current != null) {
            current.interrupt();
            try {
                current.join(2500);
            } catch (InterruptedException error) {
                Thread.currentThread().interrupt();
            }
        }
    }

    @Override
    public Health health() {
        return Health.up().withDetail("plugins", plugins).build();
    }
}
