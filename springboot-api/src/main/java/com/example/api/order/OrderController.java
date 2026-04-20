package com.example.api.order;

import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import jakarta.validation.constraints.DecimalMin;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.server.ResponseStatusException;

import java.math.BigDecimal;
import java.net.URI;
import java.time.Instant;
import java.util.List;

import static org.springframework.http.HttpStatus.NOT_FOUND;

@Tag(name = "Orders", description = "CRUD operations on orders")
@RestController
@RequestMapping("/orders")
public class OrderController {

    private final OrderService service;

    public OrderController(OrderService service) {
        this.service = service;
    }

    @Operation(summary = "List orders, optionally filtered by status")
    @GetMapping
    public List<OrderEntity> list(@RequestParam(required = false) OrderStatus status) {
        return service.list(status);
    }

    @Operation(summary = "Get a single order by id")
    @GetMapping("/{id}")
    public OrderEntity get(@PathVariable Long id) {
        return service.get(id);
    }

    @Operation(summary = "Create a new order")
    @PostMapping
    public ResponseEntity<OrderEntity> create(@RequestBody @Valid OrderCreateRequest req) {
        OrderEntity saved = service.create(req.customerName(), req.amount(), req.status(), req.createdAt());
        return ResponseEntity.created(URI.create("/orders/" + saved.getId())).body(saved);
    }

    @Operation(summary = "Update an existing order (partial fields allowed)")
    @PutMapping("/{id}")
    public OrderEntity update(@PathVariable Long id, @RequestBody @Valid OrderUpdateRequest req) {
        return service.update(id, req.customerName(), req.amount(), req.status());
    }

    @Operation(summary = "Delete an order by id")
    @DeleteMapping("/{id}")
    public ResponseEntity<Void> delete(@PathVariable Long id) {
        service.delete(id);
        return ResponseEntity.noContent().build();
    }

    @ExceptionHandler(OrderService.OrderNotFoundException.class)
    public ResponseStatusException handleNotFound(OrderService.OrderNotFoundException ex) {
        return new ResponseStatusException(NOT_FOUND, ex.getMessage());
    }

    public record OrderCreateRequest(
            @NotBlank String customerName,
            @NotNull @DecimalMin("0.00") BigDecimal amount,
            OrderStatus status,
            Instant createdAt) {}

    public record OrderUpdateRequest(
            String customerName,
            @DecimalMin("0.00") BigDecimal amount,
            OrderStatus status) {}
}
