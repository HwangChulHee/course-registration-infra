FROM maven:3.9.9-eclipse-temurin-21 AS build
WORKDIR /app
COPY pom.xml .
COPY settings.xml settings.xml
COPY src src
RUN --mount=type=cache,target=/root/.m2 mvn -B -ntp -s settings.xml -DskipTests package

FROM eclipse-temurin:21.0.9_10-jre-alpine
RUN apk add --no-cache curl && addgroup -S app && adduser -S app -G app
WORKDIR /app
COPY --from=build --chown=app:app /app/target/registration-0.1.0.jar app.jar
USER app
EXPOSE 8080
ENTRYPOINT ["java","-jar","/app/app.jar"]
