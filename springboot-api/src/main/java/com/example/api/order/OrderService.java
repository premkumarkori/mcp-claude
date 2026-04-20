package com.example.api.order;

import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.List;

@Service
@Transactional
public class OrderService {

    private final OrderRepository repo;

    public OrderService(OrderRepository repo) {
        this.repo = repo;
    }

    @Transactional(readOnly = true)
    public List<OrderEntity> list(OrderStatus status) {
        return status == null ? repo.findAll() : repo.findByStatus(status);
    }

    @Transactional(readOnly = true)
    public OrderEntity get(Long id) {
        return repo.findById(id)
                .orElseThrow(() -> new OrderNotFoundException(id));
    }

    public OrderEntity create(String customerName, BigDecimal amount, OrderStatus status, Instant createdAt) {
        return repo.save(new OrderEntity(
                customerName,
                amount,
                status == null ? OrderStatus.PENDING : status,
                createdAt == null ? Instant.now() : createdAt));
    }

    public OrderEntity update(Long id, String customerName, BigDecimal amount, OrderStatus status) {
        OrderEntity o = get(id);
        if (customerName != null) o.setCustomerName(customerName);
        if (amount != null) o.setAmount(amount);
        if (status != null) o.setStatus(status);
        return o;
    }

    public void delete(Long id) {
        if (!repo.existsById(id)) throw new OrderNotFoundException(id);
        repo.deleteById(id);
    }

    public static class OrderNotFoundException extends RuntimeException {
        public OrderNotFoundException(Long id) { super("Order %d not found".formatted(id)); }
    }
}
