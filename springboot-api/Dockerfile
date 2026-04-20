# syntax=docker/dockerfile:1.7

# --- Build stage -----------------------------------------------------------
FROM maven:3.9-eclipse-temurin-21 AS build
WORKDIR /build

# Pre-fetch deps to leverage Docker layer caching.
COPY pom.xml .
RUN mvn -B -q -e -DskipTests dependency:go-offline

COPY src ./src
RUN mvn -B -q -e -DskipTests package

# --- Runtime stage ---------------------------------------------------------
FROM eclipse-temurin:21-jre
WORKDIR /app

# Non-root user.
RUN groupadd --system app && useradd --system --gid app --home /app app
USER app

COPY --from=build /build/target/*.jar /app/app.jar

EXPOSE 8080
ENV JAVA_OPTS=""
ENTRYPOINT ["sh", "-c", "exec java $JAVA_OPTS -jar /app/app.jar"]
