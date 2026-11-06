package kr.ac.hankuk.registration;

import io.micrometer.core.instrument.*;
import java.time.Instant;
import java.util.*;
import org.springframework.context.annotation.Profile;
import org.springframework.web.bind.annotation.*;

/** Authenticated allow-list readout for the isolated benchmark only; no Actuator expansion. */
@Profile("benchmark & local")
@RestController
@RequestMapping("/api/v1/benchmark")
public class BenchmarkMetricsController {
    private final MeterRegistry registry;
    private static final Set<String> ALLOWED=Set.of(
        "jvm.memory.used","jvm.memory.committed","jvm.memory.max","jvm.gc.pause",
        "jvm.gc.memory.allocated","jvm.threads.live","jvm.threads.peak",
        "hikaricp.connections.active","hikaricp.connections.idle","hikaricp.connections.pending",
        "hikaricp.connections.max","hikaricp.connections.timeout","hikaricp.connections.acquire",
        "process.cpu.usage","process.cpu.time","system.cpu.usage");
    public BenchmarkMetricsController(MeterRegistry registry) { this.registry=registry; }
    @GetMapping("/metrics")
    Map<String,Object> metrics() {
        List<Map<String,Object>> values=new ArrayList<>();
        for(Meter meter:registry.getMeters()) {
            if(!ALLOWED.contains(meter.getId().getName())) continue;
            List<Map<String,Object>> measurements=new ArrayList<>();
            for(Measurement measurement:meter.measure()) measurements.add(Map.of("statistic",measurement.getStatistic().name(),"value",measurement.getValue()));
            Map<String,String> tags=new TreeMap<>();
            for(Tag tag:meter.getId().getTags()) tags.put(tag.getKey(),tag.getValue());
            values.add(Map.of("name",meter.getId().getName(),"tags",tags,"measurements",measurements));
        }
        return Map.of("time",Instant.now().toString(),"meters",values);
    }
}
