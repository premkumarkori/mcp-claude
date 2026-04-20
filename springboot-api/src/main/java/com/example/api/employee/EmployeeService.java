package com.example.api.employee;

import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.Instant;
import java.util.List;

@Service
@Transactional
public class EmployeeService {

    private final EmployeeRepository repo;

    public EmployeeService(EmployeeRepository repo) {
        this.repo = repo;
    }

    @Transactional(readOnly = true)
    public List<Employee> list(Instant joinedAfter) {
        return joinedAfter == null ? repo.findAll() : repo.findByJoinedAtAfter(joinedAfter);
    }

    @Transactional(readOnly = true)
    public Employee get(Long id) {
        return repo.findById(id)
                .orElseThrow(() -> new EmployeeNotFoundException(id));
    }

    public Employee create(String name, String email, Instant joinedAt) {
        return repo.save(new Employee(name, email, joinedAt == null ? Instant.now() : joinedAt));
    }

    public Employee update(Long id, String name, String email, Instant joinedAt) {
        Employee e = get(id);
        if (name != null) e.setName(name);
        if (email != null) e.setEmail(email);
        if (joinedAt != null) e.setJoinedAt(joinedAt);
        return e;
    }

    public void delete(Long id) {
        if (!repo.existsById(id)) throw new EmployeeNotFoundException(id);
        repo.deleteById(id);
    }

    public static class EmployeeNotFoundException extends RuntimeException {
        public EmployeeNotFoundException(Long id) { super("Employee %d not found".formatted(id)); }
    }
}
