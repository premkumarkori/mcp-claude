package com.example.api.employee;

import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;
import org.springframework.format.annotation.DateTimeFormat;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.server.ResponseStatusException;

import java.net.URI;
import java.time.Instant;
import java.util.List;

import static org.springframework.http.HttpStatus.NOT_FOUND;

@Tag(name = "Employees", description = "CRUD operations on employees")
@RestController
@RequestMapping("/employees")
public class EmployeeController {

    private final EmployeeService service;

    public EmployeeController(EmployeeService service) {
        this.service = service;
    }

    @Operation(summary = "List employees, optionally filtered by join date")
    @GetMapping
    public List<Employee> list(
            @RequestParam(required = false)
            @DateTimeFormat(iso = DateTimeFormat.ISO.DATE_TIME) Instant joinedAfter) {
        return service.list(joinedAfter);
    }

    @Operation(summary = "Get a single employee by id")
    @GetMapping("/{id}")
    public Employee get(@PathVariable Long id) {
        return service.get(id);
    }

    @Operation(summary = "Create a new employee")
    @PostMapping
    public ResponseEntity<Employee> create(@RequestBody @Valid EmployeeCreateRequest req) {
        Employee saved = service.create(req.name(), req.email(), req.joinedAt());
        return ResponseEntity.created(URI.create("/employees/" + saved.getId())).body(saved);
    }

    @Operation(summary = "Update an existing employee (partial fields allowed)")
    @PutMapping("/{id}")
    public Employee update(@PathVariable Long id, @RequestBody @Valid EmployeeUpdateRequest req) {
        return service.update(id, req.name(), req.email(), req.joinedAt());
    }

    @Operation(summary = "Delete an employee by id")
    @DeleteMapping("/{id}")
    public ResponseEntity<Void> delete(@PathVariable Long id) {
        service.delete(id);
        return ResponseEntity.noContent().build();
    }

    @ExceptionHandler(EmployeeService.EmployeeNotFoundException.class)
    public ResponseStatusException handleNotFound(EmployeeService.EmployeeNotFoundException ex) {
        return new ResponseStatusException(NOT_FOUND, ex.getMessage());
    }

    public record EmployeeCreateRequest(
            @NotBlank String name,
            @NotBlank @Email String email,
            Instant joinedAt) {}

    public record EmployeeUpdateRequest(
            String name,
            @Email String email,
            Instant joinedAt) {}
}
