CREATE TABLE administrative_roles (
    role_id BIGINT PRIMARY KEY
);

CREATE TABLE game_configuration (
    game_name VARCHAR(50) PRIMARY KEY,
    players_per_team INT,
    team_count INT,
    role_count INT
);


CREATE TABLE role_information (
    game_name VARCHAR(50),
    role_name VARCHAR(50),
    PRIMARY KEY (game_name, role_name),
    FOREIGN KEY (game_name) REFERENCES game_configuration(game_name) ON DELETE CASCADE
);


CREATE TABLE active_queues (
    queue_id BIGINT PRIMARY KEY,
    game VARCHAR(50),
    max_players INT,
    queue_message_id BIGINT
);

CREATE TABLE match_history (
    match_id BIGINT PRIMARY KEY,
    queue_id BIGINT,
    participants TEXT, -- formatted as "a_player1;a_player2;...|b_player1;b_player2;..."
    winning_team INT, -- 0: Alpha win, 1: Bravo win, -1: Match Canceled
    start_time TIMESTAMP,
    end_time TIMESTAMP
);