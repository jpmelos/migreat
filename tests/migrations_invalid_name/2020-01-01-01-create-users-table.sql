CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(250) NOT NULL UNIQUE CHECK (CHAR_LENGTH(username) > 0)
);

INSERT INTO users (username)
VALUES ('migreat');
